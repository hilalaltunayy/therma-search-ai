"""WiSARD iki aşamalı raporları: kaynak planı veya mevcut örnek ZIP'in gözlenen yapısı."""
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import csv
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import textwrap
import uuid

from .annotations import Sample
from .audit import file_digest, plot_sample
from .wisard import SOURCE, PairingSpec, LabelSpec, WisardArchive, inspect_wisard, match_pairs, inspect_labels, preview_text


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def comparison_rows(inspection=None, pairing=None, labels=None):
    """HIT-UAV kullanıcı ölçümlerini WiSARD kaynak beyanı/yerel örnek ölçümünden ayırır."""
    measured = 'Arşiv incelenmedi'
    sizes = 'Doğrulanmadı'
    if inspection is not None:
        measured = f"ZIP örneğinde {len(inspection['images'])} aday; {sum(r['status']=='ok' for r in inspection['images'])} okunabilir"
        sizes = ', '.join(sorted({f"{r['width']}x{r['height']} / {r['mode']} / {r['channels']} kanal"
                                 for r in inspection['images'] if r['status'] == 'ok'})) or 'Okunabilir görüntü yok'
    return [
        {'field': 'Kapsam', 'HIT_UAV': '2898 görüntü; kullanıcının gerçek Colab ölçümü',
         'WiSARD': 'Resmî sayfa beyanı: Visual 26862; Thermal 29989; 15453 çift diğer alt kümelerin içinde. Sayılar toplanmaz.'},
        {'field': 'Yerel veri', 'HIT_UAV': 'Bu çalıştırmada HIT-UAV yeniden okunmaz', 'WiSARD': measured},
        {'field': 'Boyut/kanal', 'HIT_UAV': '640x512 (kullanıcı doğrulaması); kanal modu burada yeniden ölçülmedi', 'WiSARD': sizes},
        {'field': 'Person gösterimi', 'HIT_UAV': 'Piksel xmin,ymin,w,h; Person=0 (kullanıcı doğrulaması)',
         'WiSARD': 'Doğrulanmadı' if not labels or labels['status']=='not_configured' else 'Kullanıcı onaylı normalize cx,cy,w,h TXT; yerel piksel xyxy gösterimi'},
        {'field': 'Sınıflar', 'HIT_UAV': 'Person, Car, Bicycle, OtherVehicle, DontCare',
         'WiSARD': 'Ham dosyalar/sözlük doğrulaması bekleniyor' if not labels or labels['status']=='not_configured' else json.dumps(labels['class_counts'], ensure_ascii=False)},
        {'field': 'Eşleştirme', 'HIT_UAV': 'Termal; bu iş akışında RGB eşleri yok',
         'WiSARD': 'Yöntem doğrulanmadı' if not pairing or pairing['status']=='not_configured' else f"Doğrulanan anahtar kuralıyla {len(pairing['pairs'])} çift; zaman/geometri ayrıca doğrulanmalı"},
        {'field': 'Split/flight', 'HIT_UAV': '2029/290/579 özgün train/val/test; uçuş sızıntısı ayrıca araştırılıyor',
         'WiSARD': 'Örnek tek uçuş: resmî sayfa beyanı. Mevcut split/flight bilgisi içerikten doğrulanmalı; yeni split oluşturulmaz.'},
        {'field': 'Lisans', 'HIT_UAV': 'Ayrı Zenodo kullanım koşulları geçerli; burada yeniden doğrulanmadı',
         'WiSARD': 'Resmî dağıtımın veri lisansı ve atıf/yeniden dağıtım kapsamı doğrulanmayı bekliyor'},
    ]


def run_wisard_exploration(output_root, *, archive_path=None, pairing_spec=None, label_spec=None,
                           code_revision, max_previews=3, preview_members=()):
    """Yeni run klasörüne kalıcı çıktı yazar; kaynak arşive/Drive verisine müdahale etmez.

    Varsayılan eşleştirme/etiket kapalıdır. Sadece kullanıcı onaylı format çizilir;
    desteklenmeyen JSON/XML/polygon formatı sessizce dönüştürülmez. Önizlemeler sınırlıdır.
    """
    if not isinstance(preview_members, (list, tuple)) or len(preview_members) > 12:
        raise ValueError('En fazla 12 ek metin önizleme üyesi seçin.')
    if type(max_previews) is not int or not 0 <= max_previews <= 6:
        raise ValueError('max_previews 0–6 arasında tam sayı olmalı.')
    pairing_spec, label_spec = pairing_spec or PairingSpec(), label_spec or LabelSpec()
    now = datetime.now(timezone.utc)
    output = Path(output_root) / (now.strftime('run_wisard_%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'partial', 'analysis_date_utc': now.isoformat(), 'code_revision': code_revision,
               'source': SOURCE, 'configuration': {'pairing': asdict(pairing_spec), 'labels': asdict(label_spec), 'max_previews': max_previews, 'preview_members': list(preview_members)},
               'environment': {p: version(p) for p in ('Pillow', 'matplotlib')},
               'archive_inspected': False, 'local_image_count': None,
               'limitations': [
                   'Örnek tek uçuş beyanına sahiptir; tam veri seti dağılımı veya uçuşlar arası genelleme ölçülmez.',
                   'Kanal sayısı modaliteyi kanıtlamaz; RGB modunda bir görüntü sahte renkli termal olabilir.',
                   'Eş anahtarlar fiziksel senkronizasyon veya geometrik hizalama kanıtı değildir.',
                   'Klasör/dosya adı flight/split tokenları hipotezdir; gerçek uçuş IDsi sayılmaz.',
                   'Yakın kare ve aynı uçuş sızıntısı burada dışlanamaz; yeni split üretilmez.',
                   'Boş/eksik etiket otomatik negatif değildir; etiket kalitesi görsel doğrulama ister.',
                   'Lisans adaylarının bulunması lisansın veriye uygulandığını veya koşulların kabulünü göstermez.',
               ]}
    _json(output / 'wisard_summary.json', summary)
    _json(output / 'source_and_experiment_plan.json', SOURCE)
    inspection, pairing, labels = None, None, None
    preview_files, preview_errors = [], []
    if archive_path is not None:
        with WisardArchive(archive_path) as source:
            inspection = inspect_wisard(source)
            extra_previews = []
            for member in preview_members:
                if member not in source.members:
                    raise ValueError(f'Seçilen önizleme üyesi arşivde yok: {member}')
                extra_previews.append(preview_text(source, member))
            _json(output / 'extra_metadata_previews.json', extra_previews)
            pairing = match_pairs([r['member'] for r in inspection['images']], pairing_spec)
            labels = inspect_labels(source, inspection['images'], label_spec)
            _csv(output / 'archive_inventory.csv', inspection['files'], ['member','bytes','extension','parent'])
            _csv(output / 'image_metadata.csv', inspection['images'], ['member','width','height','mode','bands','channels','status'])
            _csv(output / 'path_context_hints.csv', inspection['context_hints'], ['member','parent','split_name_tokens','flight_name_tokens','status'])
            _json(output / 'label_previews.json', inspection['label_previews'])
            _json(output / 'license_candidates.json', inspection['license_candidates'])
            _json(output / 'pairing_report.json', pairing)
            label_report = {k: v for k, v in labels.items() if k != 'boxes'}
            label_report['boxes'] = {name: [{'class_id': category, 'label': box.label, 'xyxy_pixels': list(box.xyxy)} for category, box in boxes]
                                     for name, boxes in labels['boxes'].items()}
            _json(output / 'annotation_report.json', label_report)
            _csv(output / 'matched_pairs.csv', pairing['pairs'], ['key','rgb_member','thermal_member'])
            # Aynı kullanıcı tanımlı flight tokenı farklı split tokenlarında görülüyorsa aday risk.
            contexts = defaultdict(set)
            for row in pairing['context_rows']:
                if row['flight_token'] and row['split_token']:
                    contexts[row['flight_token']].add(row['split_token'])
            overlaps = [{'flight_token': key, 'split_tokens': sorted(values), 'status': 'unverified_path_tokens'}
                        for key, values in sorted(contexts.items()) if len(values) > 1]
            summary.update(archive_inspected=True, archive={'path': str(archive_path), 'bytes': source.path.stat().st_size,
                           'mtime_ns': source.path.stat().st_mtime_ns, 'checksum_verified_in_this_run': False},
                           local_image_count=len(inspection['images']),
                           local_image_scope='Tanınan durağan görüntü uzantısı adayları; video/desteklenmeyen formatlar dönüştürülmedi.',
                           extensions=inspection['extensions'],
                           directories=inspection['directories'], image_errors=inspection['errors'],
                           pairing_status=pairing['status'], pair_count=len(pairing['pairs']) if pairing_spec.confirmed else None,
                           label_status=labels['status'], class_counts=labels['class_counts'] if label_spec.confirmed else None,
                           flight_split_overlap_candidates=overlaps,
                           flight_split_check='unverified_tokens_only' if pairing['context_rows'] else 'not_configured',
                           source_single_flight_risk='Kullanıcı tarafından bildirilen tek uçuş örneğini rastgele train/test bölmek yakın kare sızıntısı riski taşır.')
            import matplotlib.pyplot as plt
            for index, pair in enumerate(pairing['pairs'][:max_previews], start=1):
                figure, axes = plt.subplots(1, 2, figsize=(12, 5))
                try:
                    for side, axis in zip(('rgb', 'thermal'), axes):
                        member = pair[side+'_member']
                        with source.image(member) as image:
                            axis.imshow(image, cmap='gray' if image.mode != 'RGB' else None,
                                        **({'vmin':0,'vmax':255} if image.mode=='L' else {}))
                        axis.set_title(side + '\n' + textwrap.fill(member, 45), fontsize=9)
                        axis.set_axis_off()
                    figure.suptitle('Kullanıcı onaylı anahtar eşlemesi · senkronizasyon/hizalama ayrıca doğrulanmalı')
                    figure.tight_layout()
                    filename = f'pair_{index:02d}.png'
                    figure.savefig(output / filename, dpi=140)
                    preview_files.append({'file': filename, **pair})
                except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
                    preview_errors.append({'pair_key': pair['key'], 'error': str(exc)})
                finally:
                    plt.close(figure)
            image_info = {r['member']: r for r in inspection['images']}
            drawn = 0
            for member, boxes in sorted(labels['boxes'].items()):
                people = [box for category, box in boxes if category in label_spec.person_class_ids]
                if not people or drawn >= max_previews:
                    continue
                image = image_info[member]
                sample = Sample(member, image['width'], image['height'], tuple(people))
                figure = plot_sample(BytesIO(source.read(member)), sample)
                filename = f'person_boxes_{drawn+1:02d}.png'
                figure.savefig(output / filename, dpi=140)
                plt.close(figure)
                preview_files.append({'file': filename, 'source_member': member})
                drawn += 1
            if labels['class_counts']:
                from matplotlib.ticker import MaxNLocator
                figure, axis = plt.subplots(figsize=(9, 4))
                axis.yaxis.set_major_locator(MaxNLocator(integer=True))
                axis.bar(list(labels['class_counts']), list(labels['class_counts'].values()))
                axis.set(title='WiSARD örneği · onaylı etiket eşlemesinde ayrıştırılan kutular', xlabel='Kullanıcı doğrulamalı sınıf', ylabel='Kutu sayısı')
                figure.tight_layout()
                figure.savefig(output / 'class_distribution.png', dpi=140)
                plt.close(figure)
    comparisons = comparison_rows(inspection, pairing, labels)
    _csv(output / 'hit_uav_comparison.csv', comparisons, ['field','HIT_UAV','WiSARD'])
    summary.update(status='source_only' if inspection is None else
                   ('complete_with_issues' if inspection['errors'] or pairing['issues'] or labels['issues'] or preview_errors else 'complete'),
                   preview_files=preview_files, preview_errors=preview_errors,
                   outputs=[{'file': p.name, 'bytes': p.stat().st_size, 'sha256': file_digest(p)} for p in sorted(output.iterdir()) if p.name != 'wisard_summary.json'])
    _json(output / 'wisard_summary.json', summary)
    return output, summary


def run_wisard_sample_analysis(output_root, *, archive_path, code_revision, progress=print):
    """Bilinen MtErie örneği için tek çalıştırma API’si; genel keşif kapıları korunur.

    Ayrı adaptör bilinmeyen ZIP’te yalnızca envanter/tanılama üretir. Lazy import,
    eski genel rapor API’sini ve yalnızca kaynak planı kullananları etkilemez.
    """
    from .wisard_sample_reports import run_wisard_sample_analysis as run
    return run(output_root, archive_path=archive_path, code_revision=code_revision, progress=progress)
