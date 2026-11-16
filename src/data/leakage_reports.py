"""Drive veya yerel kökte yeni run: manuel inceleme, contact sheet ve sızıntı raporları."""
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import csv
from importlib.metadata import version
import json
import math
from pathlib import Path
import textwrap
import uuid
from zipfile import BadZipFile

from PIL import Image

from .audit import file_digest
from .hit_uav import SPLITS
from .hit_uav_archive import HitUAVArchive
from .leakage import ReviewConfig, compare_splits, scan_archive

PAIR_FIELDS = ['left_split', 'left_filename', 'left_member', 'right_split', 'right_filename',
               'right_member', 'classification', 'dhash_hamming', 'low_information_hash',
               'left_byte_sha256', 'right_byte_sha256', 'left_pixel_sha256', 'right_pixel_sha256']
PREVIOUS_EMPTY_COUNTS = {'train': 21, 'val': 3, 'test': 8}


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _show_member(axis, source, member):
    """Bozuk görüntüde bile contact sheet hücresi korunur; hata görünür ve raporlanır."""
    try:
        with source.image(member) as image:
            axis.imshow(image, cmap='gray' if image.mode != 'RGB' else None,
                        **({'vmin': 0, 'vmax': 255} if image.mode == 'L' else {}))
        return None
    except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
        # Sunum hatası çağıranın manifestine eklenir; eksik görüntü gizlenmez.
        axis.text(.5, .5, 'Görüntü okunamadı', ha='center', transform=axis.transAxes)
        return {'member': member, 'detail': str(exc)}


def render_review_images(source, review, pairs, output, config):
    """Yalnızca seçili boş/belirsiz görüntüler ve sınırlı sayıda çift diske yazılır."""
    import matplotlib.pyplot as plt
    errors, manifest = [], []
    for split in SPLITS:
        selected = [r for r in review if r['split'] == split]
        for start in range(0, len(selected), config.contact_page_size):
            page = selected[start:start+config.contact_page_size]
            rows = math.ceil(len(page)/4)
            figure, axes = plt.subplots(rows, 4, figsize=(13, rows*3.1), squeeze=False)
            try:
                for axis in axes.flat:
                    axis.set_axis_off()
                for axis, record in zip(axes.flat, page):
                    error = _show_member(axis, source, record['member'])
                    if error:
                        errors.append(error)
                    axis.set_title(textwrap.fill(record['filename'], 36) + '\n' + record['review_id'], fontsize=8)
                figure.suptitle(f'{split} · Anotasyon incelemesi · sayfa {start//config.contact_page_size+1}\n'
                                 'İnsan varlığı kararı kullanıcıya aittir; otomatik negatif kabul edilmez.', fontsize=12)
                figure.tight_layout(rect=(0, 0, 1, .94))
                filename = f'contact_sheet_{split}_{start//config.contact_page_size+1:02d}.png'
                figure.savefig(output / filename, dpi=160)
                manifest.append({'output': filename, 'review_ids': [r['review_id'] for r in page]})
            finally:
                plt.close(figure)
    for index, pair in enumerate(pairs[:config.max_pair_previews], start=1):
        figure, axes = plt.subplots(1, 2, figsize=(12, 5.7))
        try:
            for side, axis in zip(('left', 'right'), axes):
                error = _show_member(axis, source, pair[side+'_member'])
                if error:
                    errors.append(error)
                axis.set_axis_off()
                axis.set_title(pair[side+'_split'] + '\n' + textwrap.fill(pair[side+'_filename'], 50), fontsize=10)
            title = ('Tam eşitlik' if pair['classification'] != 'review_candidate' else 'İnceleme adayı; sızıntı kanıtı değil')
            figure.suptitle(f'{title} · {pair["classification"]}\ndHash Hamming={pair["dhash_hamming"]}; '
                             f'düşük bilgi hash={pair["low_information_hash"]}', fontsize=11)
            figure.tight_layout(rect=(0, 0, 1, .9))
            filename = f'suspicious_pair_{index:02d}.png'
            figure.savefig(output / filename, dpi=150)
            manifest.append({'output': filename, **pair})
        finally:
            plt.close(figure)
    return manifest, errors


def run_leakage_review(archive_path: Path, output_root: Path, *, code_revision: str,
                       config: ReviewConfig | None = None, progress=None):
    """Arşive salt okunur erişir; benzersiz run dizininde CSV/JSON/PNG üretir.

    Eşik yakın çift adaylarını tanımlar; tüm split dışı okunabilir çiftler taranır.
    Aday CSV limiti aşılırsa sayı ve truncation açıkça kaydedilir. Tüm exact gruplar
    JSON'da saklanır. CSV insan kararı alanları boş bırakılır; önceki CSV değiştirilmez.
    """
    config = config or ReviewConfig()
    now = datetime.now(timezone.utc)
    output = Path(output_root) / (now.strftime('run_leakage_%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    summary = {
        'status': 'partial', 'dataset_version': '1.2.1', 'zenodo_record_id': '7633134',
        'source_identity': 'Kullanıcının mevcut HIT-UAV v1.2.1 arşiv beyanı; MD5 yeniden hesaplanmadı.',
        'analysis_date_utc': now.isoformat(), 'code_revision': code_revision,
        'archive_path': str(archive_path), 'archive_bytes': Path(archive_path).stat().st_size,
        'configuration': asdict(config), 'splits_unchanged': list(SPLITS),
        'environment': {p: version(p) for p in ('Pillow', 'matplotlib')},
        'hash_methods': {
            'byte_sha256': 'Tam görüntü dosyası baytları; metadata ve kodlama farkında değişir.',
            'pixel_sha256': 'Doğal mod+boyut+çözülmüş piksel baytları (varsa transparency ve P modunda palet); EXIF dönüşümü/ton normalizasyonu uygulanmaz.',
            'dhash': 'Pillow L gri dönüşüm + LANCZOS 9x8 + yatay > karşılaştırması; 64 bit; 16-bit yoğunluklar kaybolabilir.',
        },
        'limitations': [
            'Exact: splitler arasında aynı dosya baytları veya aynı doğal mod/boyut/pikseller için doğrulanmış kopya örtüşmesi; kaynakların neden örtüştüğünü açıklamaz.',
            'dHash eşleşmesi yalnızca manuel inceleme adayıdır; görsel benzerlik tek başına veri sızıntısını kanıtlamaz.',
            'dHash yakın uçuş karelerini kaçırabilir; kırpma/döndürme/ton değişimi, aynı uçuş/konum sızıntısı ayrıca araştırılmalıdır.',
            'Tekdüze/düşük dokulu termal sahneler yanlış benzerlik üretebilir; 0 veya tüm-1 hash düşük bilgi olarak işaretlenir.',
            'Dosya adı grup adayları doğrulanmamış hipotezdir; gerçek uçuş veya çekim kimliği değildir.',
            'Sıfır ham anotasyon, görüntüde insan olmadığı anlamına gelmez; DontCare da anotasyon sayılır.',
            'Kaynak görüntü/etiket ve splitler değiştirilmedi; insan varlığı kararı ve eğitim kararları kullanıcıya aittir.',
            'SHA karşılaştırması yalnızca çözülebilen görüntüler arasında yapılır; okunamayanların bayt hashleri envanterde bulunabilir.',
        ],
    }
    _json(output / 'leakage_summary.json', summary)
    records, review, errors, annotation_hashes = scan_archive(archive_path, config, progress)
    exact, near, groups, comparisons = compare_splits(records, config)
    for index, record in enumerate(review, start=1):
        record['review_id'] = f'review-{index:04d}'
        record.update(human_present='', reviewer='', review_notes='')
    _csv(output / 'manual_review.csv', review,
         ['review_id', 'split', 'filename', 'member', 'selection_reason', 'raw_annotation_count',
          'decode_status', 'human_present', 'reviewer', 'review_notes'])
    _csv(output / 'hash_inventory.csv', records,
         ['split', 'filename', 'member', 'decode_status', 'width', 'height', 'mode',
          'byte_sha256', 'pixel_sha256', 'dhash_hex'])
    _csv(output / 'exact_duplicate_pairs.csv', exact, PAIR_FIELDS)
    _json(output / 'exact_duplicate_groups.json', groups)
    _csv(output / 'near_duplicate_candidates.csv', near, PAIR_FIELDS)
    _csv(output / 'filename_group_hypotheses.csv', records,
         ['split', 'filename', 'group_candidate', 'frame_token', 'group_status'])
    grouped = defaultdict(list)
    for record in records:
        if record['group_candidate']:
            grouped[record['group_candidate']].append(record)
    cross_groups = [{'group_candidate': name, 'status': 'unverified_filename_hypothesis',
                     'split_counts': dict(Counter(r['split'] for r in members))}
                    for name, members in sorted(grouped.items()) if len({r['split'] for r in members}) > 1]
    # Exact ve near kategorilerine ayrı önizleme kotası: near örnekleri exact listesiyle boğulmaz.
    half = (config.max_pair_previews+1)//2
    previews = exact[:half] + near[:max(0, config.max_pair_previews-min(half, len(exact)))]
    if len(previews) < config.max_pair_previews:
        previews += exact[half:half+config.max_pair_previews-len(previews)]
    with HitUAVArchive(archive_path) as source:
        image_manifest, render_errors = render_review_images(source, review, previews, output, config)
    zero_counts = {s: sum(r['split'] == s and r['selection_reason'] == 'zero_raw_annotations' for r in review) for s in SPLITS}
    summary.update(
        status='complete_with_errors' if errors or render_errors else 'complete',
        annotation_sha256=annotation_hashes, scanned_images=len(records),
        readable_images=sum(r['decode_status'] == 'ok' for r in records),
        zero_raw_annotation_counts=zero_counts,
        previous_user_empty_counts_comparison={s: {'previous_user_report': PREVIOUS_EMPTY_COUNTS[s],
            'recomputed': zero_counts[s], 'matches': zero_counts[s] == PREVIOUS_EMPTY_COUNTS[s]} for s in SPLITS},
        manual_review_rows=len(review), review_selection_reasons=dict(Counter(r['selection_reason'] for r in review)),
        comparison=comparisons, exact_group_count=len(groups),
        group_evidence_warning='Byte ve pixel grupları örtüşebilir; grup sayıları benzersiz çift sayısı değildir.',
        cross_split_filename_group_hypotheses=cross_groups,
        filename_group_not_inferred=sum(not r['group_candidate'] for r in records),
        errors=errors, render_errors=render_errors, image_manifest=image_manifest,
        near_ranking='Önce 0/tüm-1 olmayan hash; sonra Hamming uzaklığı ve deterministik dosya sırası.',
    )
    summary['outputs'] = [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': file_digest(p)}
                          for p in sorted(output.iterdir()) if p.name != 'leakage_summary.json']
    _json(output / 'leakage_summary.json', summary)
    return output, summary
