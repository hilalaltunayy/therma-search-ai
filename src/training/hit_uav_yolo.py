"""HIT-UAV normal_json -> tek sınıf YOLO kopyası; özgün kaynak/split değişmez.

Politika: sıfır HAM anotasyonlu ve herhangi bir DontCare içeren görüntüler
bütün splitlerde dışlanır. Diğer bilinen sınıflar Person hedefi dışında arka
plandır. Standart Ultralytics için ignore bölgesi uydurulmaz/kutu kırpılmaz.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image

from src.data.audit import file_digest
from src.data.hit_uav import SPLITS, PREVIOUS_COUNTS, parse_hit_uav
from src.data.hit_uav_archive import HitUAVArchive

POLICY = {
    'name': 'person_only_exclude_zero_raw_and_dontcare_v1',
    'target': {'0': 'Person'}, 'zero_raw_annotations': 'exclude_pending_human_review',
    'dontcare': 'exclude_entire_image_in_all_splits_no_ignore_support',
    'other_classes': 'omit_boxes_keep_image_as_background_for_person_task',
    'other_only_images': 'kept_as_person_background_assuming_person_annotations_complete',
    'source_splits': 'membership_preserved_in_subsets_no_repartition',
    'evaluation_scope': 'filtered_test_subset_not_full_official_test',
}
RISKS = [
    'Exploratory baseline; bağımsız saha/uçuş genellemesi ölçülmez.',
    'Kullanıcı önceki denetimde 32 sıfır ham anotasyon ve 1880 splitler arası dHash adayı bildirdi; burada dHash yeniden taranmaz.',
    'dHash adayı kesin kopya değildir; yakın kare/aynı uçuş sızıntısı test sonuçlarını iyimserleştirebilir.',
    'DontCare ve sıfır ham anotasyon dışlaması değerlendirme kapsamını değiştirir; özgün 579 görüntülük test skoru değildir.',
    'Person dışı kutular kaldırılır; kalan diğer-sınıf görüntülerinde insan etiketlerinin tamlığı varsayılır.',
]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def xyxy_to_yolo(box, width, height):
    """0 tabanlı sürekli piksel xyxy -> normalize merkez/boyut; hatada durur."""
    if width <= 0 or height <= 0:
        raise ValueError('Görüntü boyutu pozitif olmalı.')
    x1, y1, x2, y2 = map(float, box)
    if not all(math.isfinite(x) for x in (x1, y1, x2, y2)):
        raise ValueError('Sonlu kutu gerekli.')
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError('Kutu sınırları/alanı geçersiz; kırpma yapılmadı.')
    return ((x1+x2)/(2*width), (y1+y2)/(2*height), (x2-x1)/width, (y2-y1)/height)


def read_yolo(text, width, height):
    """Dönüşümden bağımsız çıktı denetimi: tek sınıf 0, sonlu normalize kutular."""
    boxes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        tokens = line.split()
        if len(tokens) != 5 or tokens[0] != '0':
            raise ValueError('YOLO çıktısı tam beş sütun ve sınıf 0 olmalı.')
        cx, cy, w, h = map(float, tokens[1:])
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in (cx, cy, w, h)) or min(w, h) <= 0:
            raise ValueError('Geçersiz normalize YOLO koordinatı.')
        x1, y1, x2, y2 = (cx-w/2)*width, (cy-h/2)*height, (cx+w/2)*width, (cy+h/2)*height
        # Dokuz basamaklı yazımın yarım pikselden çok daha küçük yuvarlama toleransı.
        if x1 < -1e-5 or y1 < -1e-5 or x2 > width+1e-5 or y2 > height+1e-5:
            raise ValueError('YOLO kutusu görüntü dışına taşıyor.')
        boxes.append([x1, y1, x2, y2])
    return boxes


def validate_prepared_dataset(root):
    """Eğitim öncesi manifest, tüm dosya hash’leri ve ters dönüşümü yeniden denetler.

    Eksik/fazla dosya, normalize satır hatası veya kaynak piksel kutusuyla uyuşmazlık
    eğitim kapısını kapatır. Bu işlev ultralytics/torch import etmez.
    """
    root = Path(root).resolve()
    manifest = json.loads((root/'dataset_manifest.json').read_text())
    if manifest['status'] not in ('validating', 'ready') or manifest['policy'] != POLICY:
        raise ValueError('Veri manifesti hazır değil veya politika uyuşmuyor.')
    selected = tuple(manifest.get('selected_splits', SPLITS))
    if selected not in (SPLITS, ('val',), ('train','val')):
        raise ValueError('Desteklenmeyen seçili split kapsamı.')
    expected_files = set()
    counts = {s: {'images': 0, 'labels': 0, 'Person': 0, 'person_background_images': 0} for s in selected}
    for row in manifest['images']:
        if row['disposition'] != 'included':
            continue
        split = row['split']
        if split not in selected:
            raise ValueError('Bilinmeyen split.')
        for field, digest in [('image_path', 'image_sha256'), ('label_path', 'label_sha256')]:
            path = (root/row[field]).resolve()
            if not path.is_relative_to(root) or not path.is_file() or file_digest(path) != row[digest]:
                raise ValueError(f'Çıktı dosyası/hash bozuk: {row[field]}')
            expected_files.add(path)
        text = (root/row['label_path']).read_text()
        boxes = read_yolo(text, row['width'], row['height'])
        originals = row['person_xyxy_pixels']
        if len(boxes) != len(originals) or any(abs(a-b) > 1e-5 for box, original in zip(boxes, originals) for a, b in zip(box, original)):
            raise ValueError('YOLO ters dönüşümü kaynak Person kutularıyla uyuşmuyor.')
        counts[split]['images'] += 1
        counts[split]['labels'] += 1
        counts[split]['Person'] += len(boxes)
        counts[split]['person_background_images'] += not boxes
    # Ultralytics eğitimde bu üç türetilmiş indeks dosyasını kendisi üretir.
    # Bunlar görüntü/etiket değildir; başka ek dosyalar hâlâ reddedilir.
    caches = {root/'labels'/f'{split}.cache' for split in SPLITS}
    actual = {p.resolve() for folder in ('images', 'labels') for p in (root/folder).rglob('*')
              if p.is_file() and p not in caches}
    if actual != expected_files:
        raise ValueError('Eksik/fazla çıktı dosyası veya yinelenen çıktı yolu.')
    if sum(c['images'] for c in counts.values()) != sum(r['disposition'] == 'included' for r in manifest['images']):
        raise ValueError('Çıktı dosyası sayımı tutarsız.')
    for split, count in counts.items():
        if count['images'] < 1 or count['Person'] < 1 or count != manifest['splits'][split]['prepared']:
            raise ValueError(f'{split}: boş split/Person veya manifest sayımı tutarsız.')
    if file_digest(root/'data.yaml') != manifest['data_yaml_sha256']:
        raise ValueError('data.yaml hash uyuşmuyor.')
    return counts


def prepare_hit_uav_yolo(archive_path, output_dir, *, code_revision, progress=print, splits=SPLITS):
    """Bütün JSON/görüntüleri doğrula; kopya üret; hatada status=failed ve exception.

    splits=('train','val') kontrollü eğitim içindir; test okunmaz.
    splits=('val',) yalnızca kaynak validation tanılaması içindir; train/test
    dosyaları okunmaz. Varsayılan eski üç-split davranışı korunur.
    output_dir yeni olmalıdır. Kaynak byte’lar değiştirilmeden kopyalanır. Çıktı
    dosya adları özgün image ID’sinden üretilir; kaynak adları manifestte korunur.
    """
    selected = tuple(splits)
    if selected not in (SPLITS, ('val',), ('train','val')):
        raise ValueError('Yalnızca özgün üç split, train+val veya yalnızca val hazırlanabilir.')
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'status': 'preparing', 'created_utc': datetime.now(timezone.utc).isoformat(),
                'code_revision': code_revision, 'dataset_version': '1.2.1',
                'source_url': 'https://zenodo.org/records/7633134',
                'source_provenance': 'Sürüm ve önceki MD5 doğrulaması kullanıcı beyanı; SHA256 bu çalıştırmada hesaplanır.',
                'policy': POLICY, 'risks': RISKS, 'selected_splits': list(selected), 'images': [], 'splits': {}, 'issues': []}
    if selected == ('train','val'):
        manifest['preparation_scope'] = 'original_train_val_only_no_test_images_or_annotations_read'
    manifest_path = output/'dataset_manifest.json'
    write_json(manifest_path, manifest)
    try:
        manifest['archive'] = {'path': str(archive_path), 'bytes': Path(archive_path).stat().st_size,
                               'sha256': file_digest(Path(archive_path)), 'publisher_checksum_verified_this_run': False}
        with HitUAVArchive(archive_path) as source:
            manifest['normal_json_root'] = source.root
            for split in selected:
                data_bytes = source.read(source.root+f'annotations/{split}.json')
                data = json.loads(data_bytes)
                parsed = parse_hit_uav(data)
                if parsed.issues:
                    manifest['issues'].extend({'split': split, **r} for r in parsed.issues)
                    raise ValueError(f'{split}: kaynak JSON kalite hatası; dönüşüm/eğitim durduruldu.')
                files = source.image_members(split)
                samples = {s.file_name: s for s in parsed.samples}
                if len(samples) != len(data['images']) or set(files) != set(samples):
                    raise ValueError(f'{split}: görüntü/JSON üyeliği tam eşleşmiyor.')
                raw_by_id = Counter(a['image_id'] for a in data['annotation'])
                ids = {r['filename']: r['id'] for r in data['images']}
                exclusions, lost = Counter(), Counter()
                source_counts, prepared = Counter(), Counter(images=0, labels=0, Person=0, person_background_images=0)
                for folder in ('images', 'labels'):
                    (output/folder/split).mkdir(parents=True)
                for name, sample in sorted(samples.items()):
                    member = files[name]
                    content = source.read(member)
                    if Path(name).suffix.lower() in ('.jpg', '.jpeg') and not content.endswith(b'\xff\xd9'):
                        raise ValueError('JPEG son işareti eksik; Ultralytics’in örtük onarımına bırakılmadı.')
                    with Image.open(BytesIO(content)) as image:
                        if image.width*image.height > 25_000_000:
                            raise ValueError('Görüntü piksel sınırı aşıldı.')
                        image.load()
                        if image.size != (640, 512) or image.size != (sample.width, sample.height):
                            raise ValueError(f'{member}: gerçek/etiket boyutu uyuşmuyor; 640x512 bekleniyor.')
                        if image.getexif().get(274, 1) != 1:
                            raise ValueError('EXIF yönlendirmesi var; örtük koordinat değişikliği yapılmadı.')
                        if image.mode not in ('L', 'RGB'):
                            raise ValueError('Desteklenmeyen görüntü modu; örtük ton dönüşümü yapılmadı.')
                    by_class = Counter(b.label for b in sample.boxes)
                    source_counts.update(by_class)
                    people = [list(b.xyxy) for b in sample.boxes if b.label == 'Person']
                    reason = ('zero_raw_annotations_pending_review' if raw_by_id[ids[name]] == 0 else
                              'contains_dontcare' if by_class['DontCare'] else '')
                    row = {'split': split, 'source_filename': name, 'source_member': member,
                           'source_image_id': ids[name], 'raw_annotation_count': raw_by_id[ids[name]],
                           'source_classes': dict(by_class), 'width': sample.width, 'height': sample.height,
                           'image_sha256': hashlib.sha256(content).hexdigest(),
                           'disposition': 'excluded' if reason else 'included', 'reason': reason,
                           'person_xyxy_pixels': people}
                    if reason:
                        exclusions[reason] += 1
                        lost[reason] += len(people)
                    else:
                        # Sayısal kaynak ID, uzantı; aynı split içinde eşsizliği parser doğruladı.
                        stem = f'image_{ids[name]}'
                        image_rel = f'images/{split}/{stem}{Path(name).suffix.lower()}'
                        label_rel = f'labels/{split}/{stem}.txt'
                        lines = ['0 '+' '.join(f'{v:.9f}' for v in xyxy_to_yolo(b, sample.width, sample.height)) for b in people]
                        if len(lines) != len(set(lines)):
                            raise ValueError('Tekrarlanan Person kutusu; Ultralytics’in sessiz dedup işlemine bırakılmadı.')
                        text = '\n'.join(lines)+('\n' if lines else '')
                        (output/image_rel).write_bytes(content)
                        (output/label_rel).write_text(text, encoding='utf-8')
                        row.update(image_path=image_rel, label_path=label_rel, label_sha256=hashlib.sha256(text.encode()).hexdigest())
                        prepared.update(images=1, labels=1, Person=len(people), person_background_images=int(not people))
                    manifest['images'].append(row)
                manifest['splits'][split] = {'source_images': len(samples), 'source_classes': dict(source_counts),
                    'annotation_sha256': hashlib.sha256(data_bytes).hexdigest(),
                    'dimensions_from_user_default': parsed.dimensions_from_default,
                    'excluded_images_by_reason': dict(exclusions), 'excluded_person_boxes_by_reason': dict(lost),
                    'prepared': dict(prepared),
                    'previous_user_counts': PREVIOUS_COUNTS[split],
                    'source_reference_matches': {'images': len(samples) == PREVIOUS_COUNTS[split]['images'],
                                                 'Person': source_counts['Person'] == PREVIOUS_COUNTS[split]['Person']}}
                if progress:
                    progress(f'{split}: {len(samples)} kaynak → {prepared["images"]} görüntü / {prepared["Person"]} Person; dışlanan: {dict(exclusions)}')
        # Byte kopyalarını yalnızca raporla; exploratory baseline için üyelik otomatik değiştirilmez.
        groups = defaultdict(list)
        for row in manifest['images']:
            if row['disposition'] == 'included':
                groups[row['image_sha256']].append({'split': row['split'], 'source_filename': row['source_filename']})
        manifest['cross_split_exact_byte_groups'] = [v for v in groups.values() if len({r['split'] for r in v}) > 1]
        yaml = f'path: {json.dumps(str(output))}\n'+''.join(
            f"{split}: {'images/'+split if split in selected else 'null'}\n" for split in SPLITS)+ 'names:\n  0: Person\n'
        (output/'data.yaml').write_text(yaml, encoding='utf-8')
        manifest.update(status='validating', data_yaml_sha256=file_digest(output/'data.yaml'))
        write_json(manifest_path, manifest)
        validate_prepared_dataset(output)
        manifest['status'] = 'ready'
        write_json(manifest_path, manifest)
        with (output/'image_dispositions.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['split','source_filename','disposition','reason','raw_annotation_count','source_classes'], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(manifest['images'])
        return output, manifest
    except Exception as exc:
        manifest.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        write_json(manifest_path, manifest)
        raise
