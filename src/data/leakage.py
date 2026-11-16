"""ZIP'te kaynakları değiştirmeden boş anotasyon, exact eşitlik ve dHash taraması.

SHA256 dosya baytlarını ve ayrıca doğal mod/boyut/pikselleri ayrı özetler.
dHash 8x8=64 bittir; 9x8 gri küçük görüntüde yatay komşuları karşılaştırır.
Hamming uzaklığı benzerlik adayı üretir; uçuş kimliği veya sızıntı kanıtı değildir.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import heapq
from io import BytesIO
from itertools import combinations
import json
from pathlib import Path
import re
from zipfile import BadZipFile

from PIL import Image

from .hit_uav import SPLITS, parse_hit_uav
from .hit_uav_archive import HitUAVArchive


@dataclass(frozen=True)
class ReviewConfig:
    dhash_threshold: int = 4
    max_near_pairs: int = 1000
    max_exact_pairs: int = 5000
    max_pair_previews: int = 12
    contact_page_size: int = 20
    # Yalnızca adlandırma hipotezi; gerçek uçuş ID'si olarak kullanılmaz.
    group_pattern: str = r'^(?P<group>.+?)[_-](?P<frame>\d+)$'

    def __post_init__(self):
        limits = {'dhash_threshold': (0, 64), 'max_near_pairs': (1, 10000),
                  'max_exact_pairs': (1, 10000), 'max_pair_previews': (0, 30),
                  'contact_page_size': (1, 40)}
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key}: {low}–{high} arasında tam sayı gerekli.')
        if 'group' not in re.compile(self.group_pattern).groupindex:
            raise ValueError('group_pattern, group adlı bir regex grubu içermeli.')


def dhash(image: Image.Image) -> int:
    """0..2**64-1 hash. Döndürme/kırpma/değişik ton eşlemelerine dayanıklılık garanti edilmez.

    Pillow convert('L') sonrası LANCZOS küçültme kullanılır; 16-bit/radyometrik
    yoğunluk bilgisi kaybolabilir. Mode ve yöntem manifestte kaydedilir.
    """
    with image.convert('L').resize((9, 8), Image.Resampling.LANCZOS) as small:
        values = small.tobytes()  # L modu: piksel başına bir bayt, toplam 9*8.
    result = 0
    for y in range(8):
        for x in range(8):
            result = (result << 1) | int(values[y*9+x] > values[y*9+x+1])
    return result


def pixel_sha256(image: Image.Image) -> str:
    """Aynı doğal mod, boyut ve çözülen piksel baytları; renk/ton normalizasyonu yok.

    Paletli görüntüde aynı indeksler farklı renk olabilir; palet ve varsa şeffaflık bilgisi de özete katılır.
    Yeniden sıkıştırılmış görüntü yalnızca çözülen pikseller birebir aynıysa eşleşir.
    """
    digest = hashlib.sha256(json.dumps({'mode': image.mode, 'size': image.size}, sort_keys=True).encode())
    digest.update(b'\0')
    digest.update(image.tobytes())
    if image.mode == 'P':
        digest.update(bytes(image.getpalette() or []))
    digest.update(repr(image.info.get('transparency')).encode())
    return digest.hexdigest()


def naming_hypothesis(filename, pattern):
    """Son sayısal tokenı frame adayı, öncesini grup hipotezi sayar; doğrulanmış uçuş değildir."""
    match = re.fullmatch(pattern, Path(filename).stem)
    return {'group_candidate': match.group('group') if match else '',
            'frame_token': (match.groupdict().get('frame') or '') if match else '',
            'group_status': 'unverified_filename_hypothesis' if match else 'not_inferred'}


def scan_archive(path: Path, config: ReviewConfig, progress=None):
    """Her görüntüyü bir kez okur/çözer. Sıfır *ham* anotasyon ile kayıp kayıt ayrılır.

    Hatalı kutular ayrıştırmada elenip boş Sample üretse bile negatif/etiketsiz
    sayılmaz: ham image_id referansları ayrıca sayılır. DontCare da anotasyondur.
    """
    records, review, errors, annotation_hashes = [], [], [], {}
    with HitUAVArchive(path) as source:
        for split in SPLITS:
            raw = source.read(source.root + f'annotations/{split}.json')
            annotation_hashes[split] = hashlib.sha256(raw).hexdigest()
            data = json.loads(raw)
            parsed = parse_hit_uav(data)
            errors.extend({'split': split, **issue} for issue in parsed.issues)
            labels = {s.file_name: s for s in parsed.samples}
            rows = {row['filename']: row for row in data['images']
                    if isinstance(row, dict) and isinstance(row.get('filename'), str)
                    and row['filename'] in labels}
            ref_counts = Counter(a['image_id'] for a in data['annotation'] if isinstance(a, dict)
                                 and type(a.get('image_id')) is int)
            for name, member in sorted(source.image_members(split).items()):
                sample = labels.get(name)
                raw_count = ref_counts[rows[name]['id']] if name in rows else None
                reason = ''
                if sample is None:
                    reason = 'missing_or_invalid_image_record'
                elif raw_count == 0:
                    reason = 'zero_raw_annotations'
                elif not sample.boxes:
                    reason = 'annotations_present_but_no_accepted_boxes'
                record = {'split': split, 'filename': name, 'member': member,
                          'raw_annotation_count': raw_count, 'selection_reason': reason,
                          'byte_sha256': '', 'pixel_sha256': '', 'dhash_hex': '',
                          'decode_status': 'unreadable', 'width': None, 'height': None, 'mode': '',
                          **naming_hypothesis(name, config.group_pattern)}
                try:
                    content = source.read(member)
                    record['byte_sha256'] = hashlib.sha256(content).hexdigest()
                    with Image.open(BytesIO(content)) as image:
                        if image.width * image.height > 25_000_000:
                            raise ValueError('Görüntü piksel limiti aşıldı.')
                        image.load()
                        value = dhash(image)
                        record.update(pixel_sha256=pixel_sha256(image), dhash_hex=f'{value:016x}',
                                      decode_status='ok', width=image.width, height=image.height, mode=image.mode)
                except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
                    errors.append({'split': split, 'file': name, 'issue': 'image_read_error', 'detail': str(exc)})
                records.append(record)
                if reason:
                    review.append(record)
            missing = set(labels) - set(source.image_members(split))
            errors.extend({'split': split, 'file': name, 'issue': 'missing_image'} for name in sorted(missing))
            if progress:
                progress(f'{split}: {len(source.image_members(split))} görüntü tarandı.')
    return records, review, errors, annotation_hashes


def compare_splits(records, config: ReviewConfig):
    """Tüm okunabilir split-dışı çiftleri CPU'da tarar; CSV boyutunu açık limitlerle sınırlar.

    Exact grupların tüm üyeleri ayrıca korunur; exact CSV ilk K çifttir. Near CSV,
    önce düşük bilgi taşımayan hash'leri, sonra en küçük Hamming uzaklığını seçer.
    Hash'i 0 veya tüm 1 olan görüntüler düşük bilgi uyarısıyla aday olarak kalır.
    """
    valid = sorted((r for r in records if r['decode_status'] == 'ok'), key=lambda r: (SPLITS.index(r['split']), r['filename']))
    by_split = {s: [(i, r, int(r['dhash_hex'], 16)) for i, r in enumerate(valid) if r['split'] == s] for s in SPLITS}
    exact_pairs, near_heap, counts = [], [], Counter()
    for left, right in combinations(SPLITS, 2):
        for i, a, hash_a in by_split[left]:
            for j, b, hash_b in by_split[right]:
                counts['compared_cross_split_pairs'] += 1
                distance = (hash_a ^ hash_b).bit_count()
                if a['byte_sha256'] == b['byte_sha256']:
                    kind = 'confirmed_identical_file_bytes'
                elif a['pixel_sha256'] == b['pixel_sha256']:
                    kind = 'confirmed_identical_decoded_pixels'
                else:
                    kind = 'review_candidate'
                low_information = hash_a in (0, 2**64-1) or hash_b in (0, 2**64-1)
                if kind != 'review_candidate':
                    counts['exact_pairs'] += 1
                    if len(exact_pairs) < config.max_exact_pairs:
                        exact_pairs.append(_pair(a, b, kind, distance, low_information))
                elif distance <= config.dhash_threshold:
                    counts['near_candidate_pairs'] += 1
                    # Küçük sıralama anahtarı daha güçlü aday; heap en kötüsünü başta tutar.
                    priority = (-int(low_information), -distance, -i, -j)
                    item = (priority, i, j, distance, low_information)
                    if len(near_heap) < config.max_near_pairs:
                        heapq.heappush(near_heap, item)
                    elif priority > near_heap[0][0]:
                        heapq.heapreplace(near_heap, item)
    near = [_pair(valid[i], valid[j], 'review_candidate', distance, low)
            for _, i, j, distance, low in sorted(near_heap, reverse=True)]
    groups = []
    for field in ('byte_sha256', 'pixel_sha256'):
        buckets = defaultdict(list)
        for record in valid:
            buckets[record[field]].append({'split': record['split'], 'filename': record['filename']})
        groups.extend({'evidence': field, 'sha256': digest, 'members': members}
                      for digest, members in sorted(buckets.items()) if len({m['split'] for m in members}) > 1)
    summary = {key: counts[key] for key in ('compared_cross_split_pairs', 'exact_pairs', 'near_candidate_pairs')}
    summary.update(exact_pairs_reported=len(exact_pairs), near_pairs_reported=len(near),
                   exact_csv_truncated=counts['exact_pairs'] > len(exact_pairs),
                   near_csv_truncated=counts['near_candidate_pairs'] > len(near),
                   excluded_unreadable_images=len(records)-len(valid))
    return exact_pairs, near, groups, summary


def _pair(a, b, kind, distance, low):
    return {'left_split': a['split'], 'left_filename': a['filename'], 'left_member': a['member'],
            'right_split': b['split'], 'right_filename': b['filename'], 'right_member': b['member'],
            'classification': kind, 'dhash_hamming': distance, 'low_information_hash': low,
            'left_byte_sha256': a['byte_sha256'], 'right_byte_sha256': b['byte_sha256'],
            'left_pixel_sha256': a['pixel_sha256'], 'right_pixel_sha256': b['pixel_sha256']}
