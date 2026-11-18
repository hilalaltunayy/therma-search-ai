"""Salt okunur, kullanıcı doğrulamalı MtErie örnek adaptörü ve kanıt hesapları.

Genel WiSARD okuyucusunun varsayılan kapıları değişmez. Yalnızca iki bilinen
klasör ve sekiz basamaklı son kare tokenı tanınır; başka yapıda şema seçilmez.
"""
from collections import Counter, defaultdict
from datetime import datetime
from io import BytesIO
from itertools import combinations
import hashlib
import math
from pathlib import Path
import re
from statistics import mean, median
from zipfile import BadZipFile

from PIL import Image

from .inventory import IMAGE_SUFFIXES
from .leakage import dhash, pixel_sha256

FOLDERS = {'IR': '210417_MtErie_Enterprise_IR_0004',
           'VIS': '210417_MtErie_Enterprise_VIS_0003'}
USER_REFERENCE = {
    'scope': 'Kullanıcının gerçek Colab ölçümü; bu çalıştırmanın sonucu değildir.',
    'archive_bytes': 1018780195,
    'IR': {'images': 264, 'person_annotations': 1006, 'empty_labels': 3,
           'missing_labels': 0, 'invalid_rows': 0, 'sample_resolution': [640, 512]},
    'VIS': {'images': 264, 'person_annotations': 1022, 'empty_labels': 3,
            'missing_labels': 0, 'invalid_rows': 0, 'sample_resolution': [3840, 2160]},
    'same_number_candidates': 263, 'IR_only': [264], 'VIS_only': [0],
}
CLASS_EVIDENCE = {
    'mapping': {'0': 'Person'},
    'basis': 'Kullanıcının gerçek örnek etiket/görsel incelemesi: sınıf 0 insanları işaretliyor.',
    'source': 'https://sites.google.com/uw.edu/wisard/',
    'paper': 'https://doi.org/10.1109/IROS47612.2022.9981298',
    'scope': 'Makale insan arama-kurtarma bağlamını destekler; ID=0 eşlemesi kullanıcı incelemesine dayanır.',
    'visual_evidence': 'Bu çalıştırmada üretilen kırmızı ground-truth kutulu PNG’ler; otomatik semantik doğrulama değildir.',
}
READ_ERRORS = (OSError, ValueError, RuntimeError, BadZipFile, Image.DecompressionBombError)


def describe(values):
    """Boş örnek için sıfır bulgu uydurmaz. Nicelikler sonlu sayılardır."""
    values = sorted(values)
    if not values:
        return {'n': 0, 'mean': None, 'median': None, 'min': None, 'max': None}
    return {'n': len(values), 'mean': mean(values), 'median': median(values),
            'min': values[0], 'max': values[-1],
            'p10': values[int((len(values)-1)*.10)], 'p90': values[int((len(values)-1)*.90)]}


def correlation(a, b):
    """Pearson r: sabit seride veya üçten az gözlemde tanımsız (None)."""
    if len(a) < 3:
        return None
    ac, bc = [x-mean(a) for x in a], [x-mean(b) for x in b]
    denominator = math.sqrt(sum(x*x for x in ac)*sum(x*x for x in bc))
    return sum(x*y for x, y in zip(ac, bc))/denominator if denominator else None


def sample_identity(member):
    path = Path(member)
    modalities = [mod for mod, folder in FOLDERS.items() if path.parent.name == folder]
    token = re.search(r'(?<!\d)(\d{8})$', path.stem)
    if len(modalities) != 1 or not token:
        return None
    return modalities[0], int(token[1])


def discover_adapter(members):
    """Bütün görüntüler bilinen yapıda, tek kökte ise otomatik şema kullanılabilir.

    Yinelenen kareler şemayı kapatmaz, ancak eşleştirmede asla ilk üye seçilmez.
    """
    images = [m for m in members if Path(m).suffix.lower() in IMAGE_SUFFIXES]
    unknown, roots, mods = [], set(), set()
    for member in images:
        identity = sample_identity(member)
        if identity is None:
            unknown.append(member)
        else:
            mods.add(identity[0])
            roots.add(str(Path(member).parent.parent))
    ok = bool(images) and not unknown and mods == {'IR', 'VIS'} and len(roots) == 1
    return {'status': 'recognized_user_verified_sample' if ok else 'unknown_structure',
            'enabled': ok, 'unknown_images': unknown, 'observed_modalities': sorted(mods),
            'roots': sorted(roots), 'folders': FOLDERS,
            'frame_rule': 'Bilinen modalite klasöründe dosya gövdesinin son sekiz basamağı.',
            'warning': None if ok else 'Bilinmeyen ZIP yapısı: etiket/eşleştirme varsayılmadı; envanter ve tanılama kaydedildi.'}


def parse_sample_labels(text, member, width=None, height=None):
    """5 sütun YOLO; tüm ID’ler gözlenir, yalnızca 0 Person olarak adlandırılır.

    Sınır dışı kutular korunur ve işaretlenir; piksel alanı/karşılaştırma bunları
    geçerli eğitim kutusu saymaz. Bozuk satırlar hiçbir zaman boş etiket sayılmaz.
    """
    boxes, issues, observed = [], [], Counter()
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        tokens = line.split()
        if tokens and re.fullmatch(r'\d+', tokens[0]):
            observed[int(tokens[0])] += 1
        try:
            if len(tokens) != 5 or not re.fullmatch(r'\d+', tokens[0]):
                raise ValueError('Negatif olmayan sınıf ID ve tam beş sütun gerekli.')
            category = int(tokens[0])
            cx, cy, w, h = map(float, tokens[1:])
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in (cx, cy, w, h)) or min(w, h) <= 0:
                raise ValueError('Sonlu normalize merkez ve pozitif boyut gerekli.')
            bounds = [cx-w/2, cy-h/2, cx+w/2, cy+h/2]
            out = min(bounds[:2]) < -1e-9 or max(bounds[2:]) > 1+1e-9
            row = {'member': member, 'line': line_no, 'class_id': category,
                   'label': 'Person' if category == 0 else f'unknown_{category}',
                   'cx': cx, 'cy': cy, 'width_normalized': w, 'height_normalized': h,
                   'width_px': w*width if width else None, 'height_px': h*height if height else None,
                   'xyxy': [v*(width if i % 2 == 0 else height) for i, v in enumerate(bounds)] if width and height else None,
                   'out_of_bounds': out}
            boxes.append(row)
            if out:
                issues.append({'member': member, 'line': line_no, 'issue': 'box_out_of_bounds'})
            if category != 0:
                issues.append({'member': member, 'line': line_no, 'issue': 'unknown_class_id', 'class_id': category})
        except (ValueError, OverflowError) as exc:
            issues.append({'member': member, 'line': line_no, 'issue': 'invalid_label_row', 'detail': str(exc)})
    return boxes, issues, observed


def scan_sample(source, adapter, progress=None):
    """Bir decode/görüntü: gerçek boyut, EXIF, dHash ve SHA; kaynak yazılmaz.

    ZIP zaman damgası dosya zamanıdır, kamera çekim/senkronizasyon zamanı değildir.
    Metadata sidecar’ları eksiksiz envantere alınır; yalnızca sınırlı metin önizlenir.
    """
    files, images, boxes, issues, metadata = [], [], {}, [], []
    enabled = adapter['enabled']
    consumed_labels = set()
    for member, size in sorted(source.members.items()):
        path = Path(member)
        files.append({'member': member, 'bytes': size, 'extension': path.suffix.lower(),
                      'zip_timestamp': str(source.archive.getinfo(member).date_time)})
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        identity = sample_identity(member) if enabled else None
        mod, frame = identity or (None, None)
        row = {'member': member, 'modality': mod, 'frame': frame, 'extension': path.suffix.lower(),
               'width': None, 'height': None, 'mode': None, 'channels': None, 'bands': None,
               'status': 'unreadable', 'label_member': None, 'label_status': 'not_interpreted',
               'person_count': None, 'annotation_count': None, 'raw_rows': None,
               'invalid_rows': None, 'out_of_bounds': None, 'observed_class_ids': {},
               'byte_sha256': None, 'pixel_sha256': None, 'dhash_hex': None,
               'exif': {}}
        try:
            data = source.read(member)
            row['byte_sha256'] = hashlib.sha256(data).hexdigest()
            with Image.open(BytesIO(data)) as image:
                if image.width*image.height > 25_000_000:
                    raise ValueError('Görüntü piksel limiti aşıldı.')
                image.load()
                exif = image.getexif()
                capture = {str(tag): str(exif[tag]) for tag in (306, 36867, 36868, 37520, 37521, 37522) if tag in exif}
                # Bazı JPEG’lerde DateTimeOriginal yalnızca EXIF alt IFD içindedir.
                if 34665 in exif:
                    nested = exif.get_ifd(34665)
                    capture.update({str(t): str(nested[t]) for t in (36867, 36868, 37520, 37521, 37522) if t in nested})
                row.update(width=image.width, height=image.height, mode=image.mode,
                           channels=len(image.getbands()), bands=','.join(image.getbands()), status='ok',
                           pixel_sha256=pixel_sha256(image), dhash_hex=f'{dhash(image):016x}', exif=capture)
        except READ_ERRORS as exc:
            issues.append({'member': member, 'issue': 'image_read_error', 'detail': str(exc)})
        if enabled:
            label = str(path.with_suffix('.txt'))
            row['label_member'] = label
            consumed_labels.add(label)
            if label not in source.members:
                row['label_status'] = 'missing'
                issues.append({'member': label, 'issue': 'missing_label'})
            else:
                try:
                    text = source.read(label, limit=262144).decode('utf-8-sig')
                    parsed, errors, observed = parse_sample_labels(text, member, row['width'], row['height'])
                    boxes[member] = parsed
                    issues.extend({**error, 'member': label} for error in errors)
                    row.update(label_status='empty' if not text.strip() else ('issues' if errors else 'ok'),
                               annotation_count=len(parsed), person_count=sum(b['class_id'] == 0 for b in parsed),
                               raw_rows=sum(bool(s.strip()) for s in text.splitlines()),
                               invalid_rows=sum(e['issue'] == 'invalid_label_row' for e in errors),
                               out_of_bounds=sum(b['out_of_bounds'] for b in parsed), observed_class_ids=dict(observed))
                except READ_ERRORS as exc:
                    row['label_status'] = 'unreadable'
                    issues.append({'member': label, 'issue': 'label_read_error', 'detail': str(exc)})
        images.append(row)
        if progress and len(images) % 50 == 0:
            progress(f'{len(images)} görüntü ve etiket incelendi.')
    counts = []
    for member in sorted(source.members):
        path = Path(member)
        if member in consumed_labels or path.suffix.lower() in IMAGE_SUFFIXES:
            continue
        if enabled and path.parent.name in FOLDERS.values() and path.suffix.lower() == '.txt' and path.name.lower() != 'count.txt':
            issues.append({'member': member, 'issue': 'orphan_label'})
        if path.suffix.lower() in {'.txt', '.json', '.xml', '.csv', '.yaml', '.yml', '.srt', '.md', '.log'}:
            try:
                with source.archive.open(member) as stream:
                    data = stream.read(65537)
                text = data[:65536].decode('utf-8-sig', errors='replace')
                metadata.append({'member': member, 'preview': text, 'truncated': len(data) > 65536,
                                 'interpretation': 'unverified_metadata_candidate'})
                if enabled and path.name.lower() == 'count.txt' and path.parent.name in FOLDERS.values():
                    mod = next(k for k, v in FOLDERS.items() if v == path.parent.name)
                    humans = re.search(r'number\s+of\s+humans\s*:\s*(\d+)', text, re.I)
                    count = re.search(r'number\s+of\s+images\s*:\s*(\d+)', text, re.I)
                    counts.append({'member': member, 'modality': mod,
                                   'declared_humans': int(humans[1]) if humans else None,
                                   'declared_images': int(count[1]) if count else None})
            except READ_ERRORS as exc:
                issues.append({'member': member, 'issue': 'metadata_read_error', 'detail': str(exc)})
    return {'files': files, 'images': images, 'boxes': boxes, 'issues': issues,
            'metadata_candidates': metadata, 'count_files': counts}


def modality_statistics(scan):
    result = {}
    for mod in FOLDERS:
        rows = [r for r in scan['images'] if r['modality'] == mod]
        objects = [b for r in rows for b in scan['boxes'].get(r['member'], [])]
        # Boyut istatistiğinde yalnızca okunabilir, sınırlar içindeki Person kutuları.
        people = [b for b in objects if b['class_id'] == 0 and not b['out_of_bounds'] and b['width_px'] is not None]
        small = {}
        for title, predicate in [('area_lt_32_squared', lambda b: b['width_px']*b['height_px'] < 32**2),
                                 ('width_lt_16', lambda b: b['width_px'] < 16),
                                 ('height_lt_16', lambda b: b['height_px'] < 16),
                                 ('both_sides_lt_16', lambda b: max(b['width_px'], b['height_px']) < 16)]:
            count = sum(predicate(b) for b in people)
            small[title] = {'count': count, 'denominator': len(people), 'fraction': count/len(people) if people else None}
        class_counts = Counter(b['class_id'] for b in objects)
        result[mod] = {'images': len(rows), 'readable_images': sum(r['status'] == 'ok' for r in rows),
                       'annotation_files': sum(r['label_status'] not in ('missing', 'not_interpreted') for r in rows),
                       'person_annotations': class_counts[0], 'parsed_class_counts': dict(class_counts),
                       'observed_class_id_rows': dict(sum((Counter(r['observed_class_ids']) for r in rows), Counter())),
                       'empty_labels': sum(r['label_status'] == 'empty' for r in rows),
                       'missing_labels': sum(r['label_status'] == 'missing' for r in rows),
                       'invalid_rows': sum(r['invalid_rows'] or 0 for r in rows),
                       'out_of_bounds': sum(r['out_of_bounds'] or 0 for r in rows),
                       'resolutions': dict(Counter(f"{r['width']}x{r['height']}" for r in rows if r['status'] == 'ok')),
                       'modes': dict(Counter(r['mode'] for r in rows if r['status'] == 'ok')),
                       'channels': dict(Counter(r['channels'] for r in rows if r['status'] == 'ok')),
                       'extensions': dict(Counter(r['extension'] for r in rows)),
                       'person_per_frame': describe([r['person_count'] for r in rows if r['label_status'] in ('ok', 'empty')]),
                       'size_statistics_denominator': len(people), 'width_px': describe([b['width_px'] for b in people]),
                       'height_px': describe([b['height_px'] for b in people]), 'small_objects': small}
    return result


def pairing_hypotheses(scan):
    """A: VIS=IR; B: VIS=IR-1. Belirsiz/tekrar anahtarlar dışlanır.

    Sayım farkı ve sayım değişimi yalnızca etiketleri sorunsuz karelerde ölçülür.
    Kapsam tüm görüntüleri paydada tutar; aynı ID veya insan sayısı senkron kanıtı değildir.
    """
    maps = {m: defaultdict(list) for m in FOLDERS}
    for row in scan['images']:
        if row['modality'] in maps:
            maps[row['modality']][row['frame']].append(row)
    duplicates = [{'modality': m, 'frame': n, 'members': [r['member'] for r in rs]}
                  for m, frames in maps.items() for n, rs in frames.items() if len(rs) != 1]
    pairs, hypotheses = [], {}
    for name, offset in [('A_same_number', 0), ('B_shift_minus_one', -1)]:
        matched, differences = [], []
        used = set()
        for frame, irs in sorted(maps['IR'].items()):
            viss = maps['VIS'].get(frame+offset, [])
            if len(irs) != 1 or len(viss) != 1:
                continue
            ir, vis = irs[0], viss[0]
            comparable = all(r['label_status'] in ('ok', 'empty') for r in (ir, vis))
            delta = ir['person_count']-vis['person_count'] if comparable else None
            record = {'hypothesis': name, 'ir_frame': frame, 'vis_frame': frame+offset,
                      'ir_member': ir['member'], 'vis_member': vis['member'],
                      'ir_people': ir['person_count'], 'vis_people': vis['person_count'],
                      'comparable_labels': comparable, 'difference_ir_minus_vis': delta,
                      'absolute_difference': abs(delta) if delta is not None else None}
            pairs.append(record)
            matched.append(record)
            used.update((ir['member'], vis['member']))
            if delta is not None:
                differences.append(delta)
        comparable = [p for p in matched if p['comparable_labels']]
        # Yalnızca her iki akışta da bir kare ilerleyen komşu eş adayları.
        changes = []
        for a, b in zip(matched, matched[1:]):
            if b['ir_frame']-a['ir_frame'] == b['vis_frame']-a['vis_frame'] == 1 and a['comparable_labels'] and b['comparable_labels']:
                changes.append((b['ir_people']-a['ir_people'], b['vis_people']-a['vis_people']))
        hypotheses[name] = {'vis_offset_from_ir': offset, 'candidate_pairs': len(matched),
                            'coverage': {m: len(matched)/sum(len(rs) for rs in maps[m].values()) if maps[m] else None for m in FOLDERS},
                            'comparable_label_pairs': len(comparable),
                            'count_difference_signed': describe(differences),
                            'count_difference_absolute': describe([abs(d) for d in differences]),
                            'difference_distribution': dict(Counter(differences)),
                            'equal_count_fraction': sum(d == 0 for d in differences)/len(differences) if differences else None,
                            'count_correlation': correlation([p['ir_people'] for p in comparable], [p['vis_people'] for p in comparable]),
                            'count_change_absolute_difference': describe([abs(a-b) for a, b in changes]),
                            'count_change_correlation': correlation([a for a, b in changes], [b for a, b in changes]),
                            'unmatched_members': [r['member'] for r in scan['images'] if r['modality'] in maps and r['member'] not in used]}
    # Sayım proxy'si: önce düşük MAE, eşitse yüksek kapsam. Karışık kanıtta açık ihtiyat.
    eligible = [k for k, v in hypotheses.items() if v['comparable_label_pairs']]
    ranked = sorted(eligible, key=lambda k: (hypotheses[k]['count_difference_absolute']['mean'], -hypotheses[k]['candidate_pairs']))
    preferred = None
    if ranked:
        first = hypotheses[ranked[0]]
        if len(ranked) == 1 or (first['count_difference_absolute']['mean'], first['candidate_pairs']) != (
                hypotheses[ranked[1]]['count_difference_absolute']['mean'], hypotheses[ranked[1]]['candidate_pairs']):
            preferred = ranked[0]
    return pairs, {'status': 'provisional_hypotheses_only', 'synchronization_confirmed': False,
                   'preferred_provisional_hypothesis': preferred,
                   'selection_rule': 'Karşılaştırılabilir etiketlerde düşük ortalama mutlak insan sayısı farkı; eşitse yüksek çift kapsamı. Eşitlikte tercih yok.',
                   'limitation': 'Sayı uyumu ve kapsam fiziksel senkronizasyon kanıtı değildir; perspektif/örtülme farkı sayımları etkiler. Metadata otomatik resmî eşleme sayılmaz.',
                   'hypotheses': hypotheses, 'duplicate_frame_keys': duplicates,
                   'same_number_frame_intersection': sorted(set(maps['IR']) & set(maps['VIS'])),
                   'IR_only_frame_numbers': sorted(set(maps['IR'])-set(maps['VIS'])),
                   'VIS_only_frame_numbers': sorted(set(maps['VIS'])-set(maps['IR']))}



def exif_pair_time_review(scan, pairs):
    """EXIF DateTimeOriginal ve varsa alt saniyeleri iki hipotezde karşılaştırır.

    Ortak saat/gecikme bilgisi bilinmez. Saniye çözünürlüklü aynı zamanlar,
    özellikle video karelerinde tek bir eşlemeyi kesinleştirmez. Değiştirme zamanı
    (306) çekim zamanı olarak kullanılmaz. Desteklenmeyen sidecar şeması çevrilmez.
    """
    times, errors = {}, []
    for row in scan['images']:
        exif = row['exif']
        raw = exif.get('36867')
        if not raw:
            continue
        try:
            timestamp = datetime.strptime(raw, '%Y:%m:%d %H:%M:%S')
            fraction = exif.get('37521', '').strip()
            if fraction and not fraction.isdigit():
                raise ValueError('EXIF alt saniye sayısal değil.')
            microseconds = int((fraction+'000000')[:6]) if fraction else 0
            times[row['member']] = timestamp.replace(microsecond=microseconds)
        except ValueError as exc:
            errors.append({'member': row['member'], 'detail': str(exc)})
    result = {}
    for name in ('A_same_number', 'B_shift_minus_one'):
        selected = [p for p in pairs if p['hypothesis'] == name and p['ir_member'] in times and p['vis_member'] in times]
        differences = [(times[p['ir_member']]-times[p['vis_member']]).total_seconds() for p in selected]
        result[name] = {'pairs_with_capture_times': len(selected),
                        'ir_minus_vis_seconds': describe(differences),
                        'absolute_time_difference_seconds': describe([abs(d) for d in differences]),
                        'identical_capture_timestamp_pairs': sum(d == 0 for d in differences)}
    return {'hypotheses': result, 'parse_errors': errors,
            'images_with_capture_timestamp': len(times),
            'images_with_subsecond_field': sum(bool(r['exif'].get('37521')) for r in scan['images']),
            'interpretation': 'EXIF saat adayı; ortak saat, zaman dilimi, kamera gecikmesi ve yayıncı eşlemesi doğrulanmadı. Saniye eşitliği kesin senkronizasyon değildir.'}


def temporal_review(scan):
    """Modalite İÇİ tüm çiftlerde hash; ardışık karelerde konum/sayım değişimleri.

    Merkez medyanı nesne kimliği/izleme değildir. Kamera hareketi, örtülme ve
    giriş/çıkışlardan etkilenir; RGB ve IR koordinatları birbirine kıyaslanmaz.
    """
    adjacent, near, groups, all_counts = [], [], [], {}
    for mod in FOLDERS:
        rows = sorted([r for r in scan['images'] if r['modality'] == mod and r['status'] == 'ok'], key=lambda r: (r['frame'], r['member']))
        for field in ('byte_sha256', 'pixel_sha256'):
            buckets = defaultdict(list)
            for r in rows:
                buckets[r[field]].append(r['member'])
            groups.extend({'modality': mod, 'kind': field, 'sha256': key, 'members': ms} for key, ms in buckets.items() if len(ms) > 1)
        for a, b in combinations(rows, 2):
            distance = (int(a['dhash_hex'], 16)^int(b['dhash_hex'], 16)).bit_count()
            if distance <= 4 or a['byte_sha256'] == b['byte_sha256'] or a['pixel_sha256'] == b['pixel_sha256']:
                near.append({'modality': mod, 'left': a['member'], 'right': b['member'], 'frame_gap': b['frame']-a['frame'],
                             'dhash_distance': distance, 'same_bytes': a['byte_sha256'] == b['byte_sha256'],
                             'same_pixels': a['pixel_sha256'] == b['pixel_sha256'],
                             'low_information': any(int(r['dhash_hex'], 16) in (0, 2**64-1) for r in (a, b))})
        for a, b in zip(rows, rows[1:]):
            centers = []
            for r in (a, b):
                people = [p for p in scan['boxes'].get(r['member'], []) if p['class_id'] == 0 and not p['out_of_bounds']]
                centers.append((median([p['cx'] for p in people]), median([p['cy'] for p in people])) if people and r['label_status'] == 'ok' else None)
            adjacent.append({'modality': mod, 'left': a['member'], 'right': b['member'],
                             'left_frame': a['frame'], 'right_frame': b['frame'], 'frame_gap': b['frame']-a['frame'],
                             'dhash_distance': (int(a['dhash_hex'], 16)^int(b['dhash_hex'], 16)).bit_count(),
                             'median_center_displacement_within_modality': math.dist(*centers) if all(centers) else None})
        all_counts[mod] = len(rows)*(len(rows)-1)//2
    return {'method': '64-bit yatay dHash, Hamming <=4; SHA256 dosya ve doğal piksel; yalnızca aynı modalite.',
            'warning': 'Yakın hash tekrar eden sahne adayıdır; düşük bilgi/tekdüze görüntüler yanlış yakınlık üretebilir. Sızıntı yokluğu veya uçuş ID kanıtlanmaz.',
            'compared_pairs': all_counts, 'near_or_exact_pairs': near, 'exact_groups': groups,
            'adjacent_frames': adjacent}
