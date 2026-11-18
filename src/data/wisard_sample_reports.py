"""Notebook 03 için tek çağrıda WiSARD örnek analizi, PNG ve akademik rapor.

Pillow ve Matplotlib dışında çalışma zamanı bağımlılığı yoktur. Veriler ZIP'te
kalır; her çağrı yeni çıktı dizini açar. Kaynak-only ve bilinmeyen şema da açıkça
raporlanır; ölçülmeyen nicelikler None kalır.
"""
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import textwrap
import uuid

from .audit import file_digest
from .wisard import SOURCE, WisardArchive
from .wisard_reports import _csv, _json, comparison_rows
from .wisard_sample import (FOLDERS, USER_REFERENCE, CLASS_EVIDENCE, READ_ERRORS,
                            discover_adapter, scan_sample, modality_statistics,
                            pairing_hypotheses, temporal_review, exif_pair_time_review)


def evenly_spaced(rows, count=10):
    """Baş/son dahil deterministik, tekrarsız zaman kapsamı; mevcutsa en az 10 kare."""
    if len(rows) <= count:
        return list(rows)
    return [rows[round(i*(len(rows)-1)/(count-1))] for i in range(count)]


def _save_plot(output, filename, draw, *, figsize=(12, 5)):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=figsize, squeeze=False)
    try:
        draw(fig, axes[0])
        fig.tight_layout()
        fig.savefig(output/filename, dpi=200)
    finally:
        plt.close(fig)


def draw_image(source, scan, member, axis):
    """Her modalitenin kendi piksel uzayında kırmızı ground-truth kutuları."""
    from matplotlib.patches import Rectangle
    with source.image(member) as image:
        axis.imshow(image, cmap='gray' if image.mode != 'RGB' else None)
    for box in scan['boxes'].get(member, []):
        if box['xyxy'] is None:
            continue
        x1, y1, x2, y2 = box['xyxy']
        axis.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, edgecolor='red', linewidth=1))
        axis.text(x1, y1, str(box['class_id']), color='red', fontsize=7)
    row = next(r for r in scan['images'] if r['member'] == member)
    axis.set_title(f"{row['modality'] or '?'} | {textwrap.fill(Path(member).name, 48)}\n"
                   f"{row['width']}x{row['height']} | labels: {row['label_status']} | Person: {row['person_count']}", fontsize=8)
    axis.set_axis_off()


def save_visuals(source, scan, stats, pairs, evidence, temporal, output, progress=None):
    """Tüm seçimler ve hata kayıtları manifestte; bozuk tek görsel diğerlerini durdurmaz."""
    import matplotlib.pyplot as plt
    selections, errors = [], []
    readable = {r['member'] for r in scan['images'] if r['status'] == 'ok'}

    def pair_plot(filename, members, caption):
        def draw(fig, axes):
            for axis, member in zip(axes, members):
                draw_image(source, scan, member, axis)
            for axis in axes[len(members):]:
                axis.set_axis_off()
            fig.suptitle(caption+'\nRed boxes = ground truth annotations (not model predictions)', fontsize=10)
        try:
            _save_plot(output, filename, draw, figsize=(14, 6))
            selections.append({'file': filename, 'members': members, 'caption': caption})
        except READ_ERRORS as exc:
            errors.append({'member': ', '.join(members), 'issue': 'preview_error', 'detail': str(exc)})

    for name in evidence['hypotheses']:
        candidates = [p for p in pairs if p['hypothesis'] == name and p['ir_member'] in readable and p['vis_member'] in readable]
        for index, pair in enumerate(evenly_spaced(candidates), 1):
            pair_plot(f'pair_{name}_{index:02d}.png', [pair['vis_member'], pair['ir_member']],
                      f"{name}: IR {pair['ir_frame']} / VIS {pair['vis_frame']} | PROVISIONAL pairing")
        if progress:
            progress(f'{name}: {min(10, len(candidates))} ground-truth çift görseli kaydedildi.')
    # Sınıf 0 semantiği için modalite başına en az bir anotasyonlu tekil örnek.
    for mod in FOLDERS:
        rows = [r for r in scan['images'] if r['modality'] == mod and r['member'] in readable and r['person_count']]
        if rows:
            pair_plot(f'ground_truth_{mod}.png', [rows[0]['member']], f'{mod} Person class 0 | user-verified semantic mapping')
    # Aynı kare numarasına göre eşleşmeyenlerin tamamı, sınır görüntüsüyle bağlamlı.
    unmatched = evidence['hypotheses']['A_same_number']['unmatched_members']
    for index, member in enumerate(unmatched, 1):
        if member in readable:
            pair_plot(f'unmatched_same_number_{index:02d}.png', [member], 'Unmatched under hypothesis A; not proof of missing capture')
    boundary_members = [m for m in unmatched if m in readable]
    if boundary_members:
        pair_plot('unmatched_boundaries_comparison.png', boundary_members[:2],
                  'Hypothesis A unmatched boundaries | comparison only, NOT a synchronized pair')
    # Boş anotasyonların tümü, sayfalı contact sheet. Bozuk dosya sessizce düşürülmez.
    empty = [r for r in scan['images'] if r['label_status'] == 'empty']
    for page, start in enumerate(range(0, len(empty), 6), 1):
        fig, axes = plt.subplots(2, 3, figsize=(15, 8))
        try:
            for ax, row in zip(axes.flat, empty[start:start+6]):
                try:
                    draw_image(source, scan, row['member'], ax)
                except READ_ERRORS:
                    ax.text(.1, .5, 'Unreadable: '+Path(row['member']).name, wrap=True)
                    ax.set_axis_off()
            for ax in list(axes.flat)[len(empty[start:start+6]):]:
                ax.set_axis_off()
            fig.suptitle('Empty annotation files: human presence NOT adjudicated; not confirmed negatives')
            fig.tight_layout()
            fig.savefig(output/f'empty_annotations_{page:02d}.png', dpi=200)
        finally:
            plt.close(fig)
    # Benzer sahnelerden en yakın iki bilgi taşıyan adayı örnekle; tablo tümünü içerir.
    for mod in FOLDERS:
        candidates = sorted([p for p in temporal['near_or_exact_pairs'] if p['modality'] == mod],
                            key=lambda p: (p['low_information'], p['dhash_distance'], -p['frame_gap'], p['left']))
        for i, pair in enumerate(candidates[:2], 1):
            pair_plot(f'scene_similarity_{mod}_{i:02d}.png', [pair['left'], pair['right']],
                      f"{mod} within-stream scene candidate | dHash={pair['dhash_distance']} | low information={pair['low_information']}")

    def class_chart(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            counts = stats[mod]['parsed_class_counts']
            ax.bar([str(k) for k in counts], list(counts.values()))
            ax.set(title=mod+' parsed annotation classes', xlabel='Class ID (0 = Person)', ylabel='Annotations')
    _save_plot(output, 'class_distribution.png', class_chart)

    def count_chart(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            rows = [r for r in scan['images'] if r['modality'] == mod and r['label_status'] in ('ok', 'empty')]
            counts = Counter(r['person_count'] for r in rows)
            ax.bar(list(counts), list(counts.values()))
            ax.set(title=mod+' people per frame (clean labels)', xlabel='Person annotations / frame', ylabel='Frames')
    _save_plot(output, 'people_per_frame.png', count_chart)

    def sizes(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            people = [b for r in scan['images'] if r['modality'] == mod for b in scan['boxes'].get(r['member'], [])
                      if b['class_id'] == 0 and b['width_px'] is not None and not b['out_of_bounds']]
            ax.hist([[b['width_px'] for b in people], [b['height_px'] for b in people]], bins=25, label=['width', 'height'])
            ax.legend()
            ax.set(title=mod+' valid Person box sizes', xlabel='Pixels in original image', ylabel='Annotations')
    _save_plot(output, 'bbox_width_height.png', sizes)

    def small(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            values = stats[mod]['small_objects']
            ax.bar(range(len(values)), [v['fraction']*100 if v['fraction'] is not None else 0 for v in values.values()])
            ax.set_xticks(range(len(values)), ['area<32²', 'width<16', 'height<16', 'both<16'])
            ax.set(title=f"{mod} small Person boxes | n={stats[mod]['size_statistics_denominator']}", ylabel='Percent of valid boxes')
            ax.tick_params(axis='x', labelsize=8)
            if not stats[mod]['size_statistics_denominator']:
                ax.text(.1, .5, 'No measurable valid boxes', transform=ax.transAxes)
    _save_plot(output, 'small_person_statistics.png', small)

    def difference(fig, axes):
        for (name, h), ax in zip(evidence['hypotheses'].items(), axes):
            counts = h['difference_distribution']
            ax.bar(list(counts), list(counts.values()))
            ax.set(title=f"{name}\nMAE={h['count_difference_absolute']['mean']}", xlabel='IR count - VIS count', ylabel='Comparable pairs')
    _save_plot(output, 'pairing_count_differences.png', difference)

    def sequence(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            rows = sorted([r for r in scan['images'] if r['modality'] == mod and r['label_status'] in ('ok', 'empty')], key=lambda r: r['frame'])
            ax.plot([r['frame'] for r in rows], [r['person_count'] for r in rows], marker='.', markersize=2)
            ax.set(title=mod+' frame sequence', xlabel='Frame number (not timestamp)', ylabel='Person annotations')
    _save_plot(output, 'temporal_person_counts.png', sequence)

    def transitions(fig, axes):
        for mod, ax in zip(FOLDERS, axes):
            rows = [r for r in temporal['adjacent_frames'] if r['modality'] == mod and r['frame_gap'] == 1]
            ax.plot([r['right_frame'] for r in rows], [r['dhash_distance'] for r in rows], label='dHash distance')
            ax.set(title=mod+' consecutive frames', xlabel='Right frame', ylabel='dHash Hamming distance')
            other = ax.twinx()
            other.plot([r['right_frame'] for r in rows], [r['median_center_displacement_within_modality'] for r in rows], color='orange')
            other.set_ylabel('Median center displacement (within modality)', color='darkorange', fontsize=8)
    _save_plot(output, 'temporal_similarity_and_positions.png', transitions)
    return selections, errors


def report_markdown(summary, evidence, quality, comparisons, output):
    """Kesin bulgu, kullanıcı/kaynak beyanı ve hipotez ayrı raporlanır."""
    stats = summary.get('modalities', {})
    if not stats:
        reason = summary['adapter'].get('warning') or summary['status']
        lines = ['# WiSARD analiz tanılama raporu',
                 f"Durum: {summary['status']}. {reason}",
                 f"Kod: {summary['code_revision']}; UTC: {summary['analysis_date_utc']}",
                 f"Arşiv okundu: {summary['archive_inspected']}; görüntü adayı: {summary['local_image_count']}.",
                 'Bu çalıştırmada anotasyon, eşleştirme ve sızıntı analizi tamamlanmadı. '
                 'Bilinmeyen yapıda şema varsayılmadı. Boş CSV ölçülen sıfır olarak yorumlanmamalıdır.',
                 f"Sorunlar: {json.dumps(quality['issues'], ensure_ascii=False)}"]
        for heading in ['Veri seti ve kaynağı', 'Örnek arşivin yapısı', 'IR/VIS görüntü özellikleri',
                        'Etiket yapısı', 'Nesne boyutu ve sınıf istatistikleri', 'Eşleştirme hipotezleri',
                        'Veri kalitesi', 'Veri sızıntısı ve sınırlılıklar', 'HIT-UAV karşılaştırması',
                        'YOLO11s veri hazırlama önerileri']:
            lines += [f'\n## {heading}', 'Ölçüme dayalı sonuç üretilmedi; tanılama JSON/CSV dosyalarına bakınız.']
        lines += [f"Kaynak: {SOURCE['url']}; kullanıcı referansları wisard_summary.json içinde ayrı saklanır.",
                  'Fiziksel senkronizasyon kesinleşmedi; eğitim veya rastgele split oluşturulmadı.']
        return '\n'.join(lines)+'\n'
    lines = [
        '# WiSARD örnek veri seti: keşif ve doğrulama raporu',
        f"\nÇalıştırma (UTC): {summary['analysis_date_utc']} · Kod: `{summary['code_revision']}` · Durum: `{summary['status']}`",
        '\n## 1. Veri seti ve kaynağı',
        f"[WiSARD]({SOURCE['url']}), IROS 2022, [makale](https://doi.org/{SOURCE['doi']}). "
        'Resmî sayfanın kullanıcı tarafından bildirilen kapsamı: 26.862 görsel ve 29.989 termal görüntü; '
        '15.453 eşzamanlı çift bu koleksiyonların alt kümesidir. Bu değerler bu çalıştırmada ölçülmemiştir. '
        'Lisans, dağıtım sürümü ve yayıncı checksum’ı bağımsız doğrulanmamıştır.',
        '\n## 2. Gerçek örnek arşivin yapısı',
        f"Bu çalıştırmada arşiv incelendi: **{summary['archive_inspected']}**. "
        f"Görüntü adayı: {summary['local_image_count']}; tanılama: `{summary['adapter']['status']}`. "
        'Tam dosya envanteri `archive_inventory.csv` içindedir. Veriler değiştirilmemiştir.',
        'Kullanıcının önceki ölçümü 1.018.780.195 bayt, IR/VIS başına 264 görüntü ve 265 TXT’dir. '
        'Bunlar bu çalıştırmanın bulguları yerine kullanılmamıştır. `count.txt` görüntü etiketi sayılmamıştır.',
        '\n## 3. IR/VIS görüntü özellikleri',
        '\n| Modalite | Görüntü / okunabilir | Çözünürlük (ölçülen) | Mod | Kanal | Uzantı |\n|---|---:|---|---|---|---|',
    ]
    for mod, s in stats.items():
        lines.append(f"| {mod} | {s['images']} / {s['readable_images']} | {s['resolutions']} | {s['modes']} | {s['channels']} | {s['extensions']} |")
    lines += [
        '\n## 4. Etiket yapısı',
        'Doğrulanan örnek adaptörü beş sütunlu normalize YOLO `class_id center_x center_y width height` '
        'gösterimini okur. Örnek kullanıcı satırı: `0 0.337406 0.358465 0.042969 0.069444`. '
        'ID=0 için Person anlamı kullanıcının gerçek etiket/görsel incelemesine dayanır; makale arama-kurtarma '
        'bağlamını destekler, sayısal ID sözlüğünü bağımsız doğrulamaz. `class_semantics.json` kaynak ayrımını kaydeder. '
        'Diğer sınıf ID’leri sayılır ve bilinmeyen olarak işaretlenir. **Kırmızı kutular ground truth’tur; model tahmini değildir.** '
        'Kutular kırpılmamış; sınır dışı satırlar işaretlenmiştir.',
        '\n## 5. Nesne boyutu ve sınıf istatistikleri',
        'Aşağıdaki sayımlar ayrı modalitelerdeki anotasyon toplamlarıdır. Benzersiz kişi sayısı değildir; '
        'RGB ile termal toplamları birleştirilerek benzersiz insan sayısı hesaplanamaz. '
        'Piksel boyut istatistikleri yalnızca okunabilir görüntüdeki sınırlar içi Person kutularını kapsar. '
        'Küçük nesne tanımları: alan<32² piksel², genişlik<16, yükseklik<16 ve her iki kenar<16 piksel. '
        'Bu operasyonel eşikler algılama başarısı ölçümü değildir; modaliteler arası farklı piksel ölçekleri korunmuştur.',
    ]
    for mod, s in stats.items():
        lines += [f"\n### {mod}", f"Person anotasyonu: {s['person_annotations']}; ayrıştırılan sınıflar: {s['parsed_class_counts']}. "
                  f"Ham satırlarda gözlenen ID’ler: {s['observed_class_id_rows']}. "
                  f"İnsan/kare: {s['person_per_frame']}. "
                  f"Genişlik (px): {s['width_px']}; yükseklik (px): {s['height_px']}. "
                  f"Boyut paydası: {s['size_statistics_denominator']}. Küçük nesneler: {json.dumps(s['small_objects'], ensure_ascii=False)}."]
    lines += ['\n## 6. Eşleştirme hipotezleri ve belirsizlikler',
              'A: IR n ↔ VIS n. B: IR n ↔ VIS n−1. Tüm kare numaraları taranmış, yinelenen anahtarlar '
              'eşleştirmeden dışlanmıştır. `pairing_hypotheses.csv` her adayın sayım farkını, '
              '`pairing_evidence.json` kapsamı, ortalama/medyan ve tam fark dağılımını içerir. '
              'Sayım karşılaştırmaları yalnızca sorunsuz etiketli kareleri kapsar.']
    for name, h in evidence.get('hypotheses', {}).items():
        lines.append(f"\n- **{name}**: {h['candidate_pairs']} aday; kapsam IR/VIS: {h['coverage']}; "
                     f"karşılaştırılabilir etiket: {h['comparable_label_pairs']}; "
                     f"işaretli fark: {h['count_difference_signed']}; mutlak fark: {h['count_difference_absolute']}; "
                     f"fark dağılımı: {h['difference_distribution']}; eşit sayım oranı: {h['equal_count_fraction']}; "
                     f"sayım korelasyonu: {h['count_correlation']}; ardışık sayım değişimi mutlak farkı: {h['count_change_absolute_difference']}.")
    lines += [f"\nEn güçlü **geçici** aday: {evidence.get('preferred_provisional_hypothesis') or 'Ayırt edilemedi'}. "
              f"Seçim kuralı: {evidence.get('selection_rule', 'Şema doğrulanmadı')}. "
              '**Fiziksel senkronizasyon kesinleşmedi.** Aynı insan sayısı veya kare numarası tek başına kanıt değildir. '
              'Kameraların perspektif ve çözünürlükleri farklıdır; kutu koordinatları modaliteler arasında doğrudan karşılaştırılmamıştır. '
              'Konum değişimleri her modalitenin kendi ardışık karelerinde ayrı hesaplanmıştır; nesne kimliği veya takip sonucu değildir. '
              'Metadata/EXIF adayları kaydedilmiş, dosya ZIP tarihleri çekim zamanı sayılmamıştır. '
              'Genel metadata içeriklerinden resmî eşleme otomatik türetilmemiştir. '
              'Kesin eşleme için yayıncı eşleme belgesi veya ortak saat temelli, gecikmesi doğrulanmış zaman bilgisi gerekir.',
              f"EXIF çekim zamanı karşılaştırması: {json.dumps(evidence.get('capture_time_evidence', {}), ensure_ascii=False)}.",
              '\n## 7. Veri kalitesi',
              f"Benzersiz problemli dosya: {quality['problem_file_count']}; problem kayıtları: {quality['issue_counts']}. "
              'Tüm kayıtlar `data_quality.json` içindedir. Boş TXT listesi `empty_annotations.csv` ve PNG contact sheet’lerinde bulunur. '
              '**Boş anotasyon kesin negatif anlamına gelmez.** Otomatik insan var/yok kararı verilmemiştir.',
              f"`count.txt` kontrolü: {json.dumps(quality.get('count_txt_checks', []), ensure_ascii=False)}.",
              '\n## 8. Veri sızıntısı ve deney sınırlılıkları',
              'Örneğin tek uçuş içerdiği kaynak/kullanıcı beyanıdır; dosya adlarından yeni uçuş kimliği üretilmemiştir. '
              'Modalite içinde bütün okunabilir çiftlerde dosya/piksel SHA256 ve 64-bit dHash (Hamming≤4) taranmıştır. '
              'Ardışık kare farkları ve uzak karelerdeki tekrar eden sahne adayları kaydedilmiştir. '
              'Düşük bilgi içeren tekdüze sahneler yanlış benzerlik üretebilir; düşük hash farkı sızıntıyı kanıtlamaz, '
              'yüksek fark sızıntıyı dışlamaz. Rastgele train/val/test ayrımı yapılmamıştır. '
              'RGB ve termal çiftler bağımsız örnek kabul edilmemelidir. Tek uçuş örneği bağımsız uçuş genellemesi ölçemez.',
              '\n## 9. HIT-UAV ile karşılaştırma',
              'HIT-UAV bu çalıştırmada yeniden okunmamıştır; aşağıdaki bilgiler önceki kullanıcı ölçümü/kaynak notudur.',
              '\n| Özellik | HIT-UAV (önceki bilgi) | WiSARD |\n|---|---|---|']
    lines += [f"| {r['field']} | {r['HIT_UAV']} | {r['WiSARD']} |" for r in comparisons]
    lines += ['\n## 10. YOLO11s için veri hazırlama önerileri',
              'Önce bozuk/eksik etiketler ve boş anotasyonların insan varlığı incelemesi tamamlanmalıdır. '
              'Lisans/sürüm ve sınıf sözlüğü doğrulanmalı; orijinal etiketler korunarak dönüşüm manifesti hazırlanmalıdır. '
              'IR ve VIS farklı piksel ölçeklerinde ayrı raporlanmalı; yeniden boyutlandırma, küçük insanların kaybı '
              've gerekiyorsa dilimleme yalnızca eğitim bölümü üzerinde seçilmelidir. '
              'Kesin eşleme elde edilmeden füzyon için eşzamanlı ground truth iddiası kullanılmamalıdır. '
              'Gelecekte gerçek uçuş/sekans/konum gruplarıyla ayrım tasarlanmalı; yakın kareler ve modalite eşleri '
              'aynı grupta tutulmalı, bağımsız uçuş test verisi ayrılmalıdır. '
              'Tek uçuş örneği geliştirme ve şema kontrolü içindir. Eğitim veya değerlendirme yapılmamıştır; '
              'eğitim ve split protokolünün son kararı kullanıcıya aittir.',
              '\n## Otomatik kaydedilen şekiller',
              'Her iki hipotezde yeterli okunabilir aday varsa en az on farklı kare seçilir. '
              'Seçimler `visual_manifest.json` içindedir. Şekiller 200 DPI PNG olarak kaydedilir.']
    for path in sorted(output.glob('*.png')):
        lines.append(f'\n![{path.stem}]({path.name})')
    return '\n'.join(lines)+'\n'


def run_wisard_sample_analysis(output_root, *, archive_path, code_revision, progress=print):
    """Notebook’un tek çalıştırma giriş noktası; kullanıcı regex/Spec doldurmaz."""
    now = datetime.now(timezone.utc)
    output = Path(output_root)/(now.strftime('run_wisard_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'initializing', 'analysis_date_utc': now.isoformat(), 'code_revision': code_revision,
               'environment': {'python': platform.python_version(), **{p: version(p) for p in ('Pillow', 'matplotlib')}},
               'source': SOURCE, 'user_reference': USER_REFERENCE, 'archive_inspected': False,
               'local_image_count': None, 'modalities': {}, 'archive': None,
               'adapter': {'status': 'not_inspected', 'enabled': False}}
    scan = {'files': [], 'images': [], 'boxes': {}, 'issues': [], 'count_files': [], 'metadata_candidates': []}
    evidence = {'status': 'not_analyzed', 'synchronization_confirmed': False, 'hypotheses': {}, 'preferred_provisional_hypothesis': None}
    temporal = {'adjacent_frames': [], 'near_or_exact_pairs': [], 'exact_groups': []}
    pairs, visual_manifest = [], []
    if archive_path is not None:
        try:
            with WisardArchive(archive_path) as source:
                adapter = discover_adapter(source.members)
                summary['adapter'] = adapter
                if progress:
                    progress(adapter['status']+(': '+adapter['warning'] if adapter['warning'] else ''))
                scan = scan_sample(source, adapter, progress)
                summary.update(archive_inspected=True, local_image_count=len(scan['images']),
                               archive={'path': str(archive_path), 'bytes': source.path.stat().st_size,
                                        'sha256': file_digest(source.path), 'publisher_checksum_verified': False})
                if adapter['enabled']:
                    stats = modality_statistics(scan)
                    summary['modalities'] = stats
                    pairs, evidence = pairing_hypotheses(scan)
                    evidence['capture_time_evidence'] = exif_pair_time_review(scan, pairs)
                    temporal = temporal_review(scan)
                    for duplicate in evidence['duplicate_frame_keys']:
                        scan['issues'].extend({'member': m, 'issue': 'duplicate_frame_key'} for m in duplicate['members'])
                    visual_manifest, errors = save_visuals(source, scan, stats, pairs, evidence, temporal, output, progress)
                    scan['issues'].extend(errors)
        except (FileNotFoundError, KeyError, *READ_ERRORS) as exc:
            scan['issues'].append({'member': str(archive_path), 'issue': 'archive_or_analysis_error', 'detail': str(exc)})
            summary['status'] = 'failed_with_diagnostics'
    quality = {'issues': scan['issues'], 'issue_counts': dict(Counter(r['issue'] for r in scan['issues'])),
               'problem_file_count': len({r['member'] for r in scan['issues']}),
               'empty_annotations_are_confirmed_negatives': False, 'count_txt_checks': [],
               'reference_comparisons': [], 'counting_scope': 'Anotasyon toplamı; benzersiz insan değil. Modaliteler ayrı.'}
    if summary['adapter']['enabled'] and summary['modalities']:
        for mod, stats in summary['modalities'].items():
            counts = [r for r in scan['count_files'] if r['modality'] == mod]
            if not counts:
                issue = {'member': FOLDERS[mod]+'/count.txt', 'issue': 'missing_count_txt'}
                scan['issues'].append(issue)
            for row in counts:
                quality['count_txt_checks'].append({**row, 'measured_images': stats['images'],
                    'measured_humans': stats['person_annotations'],
                    'matches': row['declared_images'] == stats['images'] and row['declared_humans'] == stats['person_annotations']})
                if not quality['count_txt_checks'][-1]['matches']:
                    scan['issues'].append({'member': row['member'], 'issue': 'count_txt_mismatch'})
            quality['reference_comparisons'].extend({'modality': mod, 'metric': key, 'user_reference': value,
                'measured': stats[key], 'matches': stats[key] == value}
                for key, value in USER_REFERENCE[mod].items() if key != 'sample_resolution')
        quality['reference_comparisons'].append({'metric': 'archive_bytes', 'user_reference': USER_REFERENCE['archive_bytes'],
            'measured': summary['archive']['bytes'], 'matches': summary['archive']['bytes'] == USER_REFERENCE['archive_bytes']})
    quality.update(issue_counts=dict(Counter(r['issue'] for r in scan['issues'])),
                   problem_file_count=len({r['member'] for r in scan['issues']}))
    evidence['metadata_review'] = {'sidecar_candidate_count': len(scan['metadata_candidates']),
                                  'images_with_exif_time_fields': sum(bool(r['exif']) for r in scan['images']),
                                  'official_pair_mapping_verified': False,
                                  'status': 'Candidates saved, schema/clock not independently verified; no synchronization claim.'}
    if summary['status'] != 'failed_with_diagnostics':
        summary['status'] = ('source_only' if archive_path is None else 'unknown_structure' if not summary['adapter']['enabled']
                             else 'complete_with_issues' if scan['issues'] else 'complete_provisional_pairing')
    summary.update(problem_file_count=quality['problem_file_count'],
                   pairing_status=evidence['status'],
                   preferred_provisional_hypothesis=evidence['preferred_provisional_hypothesis'],
                   pairing_candidate_counts={k: v['candidate_pairs'] for k, v in evidence['hypotheses'].items()},
                   output_directory=str(output))
    # Eski karşılaştırma tablosunun HIT-UAV kaynak bilgileri korunur, WiSARD yerel ölçümü güncellenir.
    inspection = {'images': scan['images']} if summary['archive_inspected'] else None
    comparisons = comparison_rows(inspection)
    if summary['modalities']:
        for row in comparisons:
            if row['field'] == 'Person gösterimi':
                row['WiSARD'] = 'Normalize YOLO cx,cy,w,h; sınıf 0 Person (kullanıcı görsel doğrulaması)'
            elif row['field'] == 'Sınıflar':
                row['WiSARD'] = str({m: s['parsed_class_counts'] for m, s in summary['modalities'].items()})
            elif row['field'] == 'Eşleştirme':
                row['WiSARD'] = str(summary['pairing_candidate_counts'])+'; geçici, senkronizasyon kesinleşmedi'
    # Tüm istenen dosyalar tanılama modunda da başlıklarıyla oluşur; None ölçülmedi demektir.
    _csv(output/'archive_inventory.csv', scan['files'], ['member', 'bytes', 'extension', 'zip_timestamp'])
    image_rows = [{**r, 'exif': json.dumps(r['exif']), 'observed_class_ids': json.dumps(r['observed_class_ids'])} for r in scan['images']]
    _csv(output/'image_metadata.csv', image_rows, list(image_rows[0]) if image_rows else ['member','status'])
    annotations = [{**r, 'class_counts': json.dumps(dict(Counter(b['class_id'] for b in scan['boxes'].get(r['member'], []))))} for r in image_rows]
    _csv(output/'annotation_statistics.csv', annotations, ['member','modality','frame','label_member','label_status','raw_rows',
         'annotation_count','person_count','class_counts','invalid_rows','out_of_bounds'])
    object_rows = [dict(b, xyxy=json.dumps(b['xyxy'])) for bs in scan['boxes'].values() for b in bs]
    _csv(output/'bounding_boxes.csv', object_rows, ['member','line','class_id','label','cx','cy','width_normalized','height_normalized','width_px','height_px','xyxy','out_of_bounds'])
    _csv(output/'empty_annotations.csv', [r for r in image_rows if r['label_status'] == 'empty'], ['member','modality','frame','label_member','status'])
    _csv(output/'pairing_hypotheses.csv', pairs, list(pairs[0]) if pairs else ['hypothesis','ir_frame','vis_frame','ir_member','vis_member'])
    _csv(output/'temporal_adjacency.csv', temporal['adjacent_frames'], list(temporal['adjacent_frames'][0]) if temporal['adjacent_frames'] else ['modality','left','right'])
    _csv(output/'scene_similarity_pairs.csv', temporal['near_or_exact_pairs'], list(temporal['near_or_exact_pairs'][0]) if temporal['near_or_exact_pairs'] else ['modality','left','right'])
    _csv(output/'hit_uav_comparison.csv', comparisons, ['field','HIT_UAV','WiSARD'])
    _json(output/'pairing_evidence.json', evidence)
    _json(output/'data_quality.json', quality)
    _json(output/'metadata_candidates.json', scan['metadata_candidates'])
    _json(output/'temporal_review.json', {k: v for k, v in temporal.items() if k != 'near_or_exact_pairs'})
    _json(output/'class_semantics.json', CLASS_EVIDENCE)
    _json(output/'visual_manifest.json', visual_manifest)
    (output/'wisard_analysis_report.md').write_text(report_markdown(summary, evidence, quality, comparisons, output), encoding='utf-8')
    summary['outputs'] = [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': file_digest(p)} for p in sorted(output.iterdir())]
    _json(output/'wisard_summary.json', summary)
    return output, summary


def turkish_summary(output, summary):
    """Notebook’un son hücresinde kısa, veriye bağlı Türkçe çıktı."""
    stats = summary['modalities']
    counts = '; '.join(f"{m}: {s['person_annotations']}" for m, s in stats.items()) or 'Ölçülmedi'
    return '\n'.join([
        f"Analiz durumu: {summary['status']}",
        f"Analiz edilen görüntü: {summary['local_image_count'] if summary['archive_inspected'] else 'Ölçülmedi'}",
        f"İnsan anotasyonu (modaliteler ayrı; benzersiz kişi değil): {counts}",
        f"Problemli dosya: {summary['problem_file_count']} (boş anotasyon tek başına hata/negatif değildir)",
        f"RGB–termal çift adayları: {summary['pairing_candidate_counts'] or 'Ölçülmedi'}",
        f"Daha güçlü geçici hipotez: {summary['preferred_provisional_hypothesis'] or 'Ayırt edilemedi'}",
        'Kesinleşmeyenler: fiziksel senkronizasyon, resmî eşleme, boş etiketlerin negatifliği, bağımsız uçuş genellemesi ve lisans/sürüm.',
        f"Raporlar: {output}",
    ])
