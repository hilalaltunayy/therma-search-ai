"""WiSARD'ın doğrulanmış MtErie adaptörüyle yalnızca IR değerlendirme kopyası.

VIS üyeleri okunmaz/çözülmez; eşleştirme ve zaman senkronizasyonu kullanılmaz.
Boş TXT belirsizdir, skor dışıdır. Herhangi bir bozuk IR kayıt bütün skorlamayı
engeller; kısmi temiz alt kümede sessiz başarı sonucu üretilmez.
"""
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image

from src.data.inventory import IMAGE_SUFFIXES
from src.data.wisard import WisardArchive
from src.data.wisard_sample import FOLDERS, READ_ERRORS, parse_sample_labels, sample_identity


def prepare_ir_evaluation(archive_path, output_dir, progress=print):
    """Yeni yerel dizine byte-eşit IR kopyaları; kaynakta hiçbir yazma yok.

    Fonksiyon tüm doğrulama sorunlarını manifestte döndürür. status=invalid ise
    çağıran çıkarımı ve mAP'ı durdurmalıdır. Orijinal boş etiketler değiştirilmez.
    """
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for folder in ('images/eval', 'labels/eval', 'review_images'):
        (output/folder).mkdir(parents=True)
    result = {'status': 'invalid', 'modality': 'IR', 'images': [], 'issues': [],
              'policy': 'empty_annotation_excluded_pending_review; any_invalid_IR_blocks_scoring',
              'source_ir_image_candidates': 0, 'source_person_annotations_parsed': 0,
              'empty_annotation_files': 0, 'included_images': 0, 'excluded_images': 0}
    with WisardArchive(archive_path) as source:
        ir_images = [m for m in source.members if FOLDERS['IR'] in Path(m).parts
                     and Path(m).suffix.lower() in IMAGE_SUFFIXES]
        result['source_ir_image_candidates'] = len(ir_images)
        roots, frames, label_users = set(), {}, set()
        if not ir_images:
            result['issues'].append({'member': '', 'issue': 'no_known_IR_images'})
        for member in sorted(ir_images):
            identity = sample_identity(member)
            row = {'member': member, 'frame': None, 'image_path': None, 'label_member': None,
                   'included': False, 'reason': 'invalid_IR_record', 'width': None, 'height': None,
                   'mode': None, 'image_sha256': None, 'label_sha256': None,
                   'person_count': None, 'boxes': []}
            result['images'].append(row)
            try:
                if identity is None or identity[0] != 'IR':
                    raise ValueError('Doğrulanmış IR klasörü/sekiz basamaklı kare örüntüsüyle uyuşmuyor.')
                frame = identity[1]
                roots.add(str(Path(member).parent))
                if frame in frames:
                    raise ValueError(f'Tekrarlanan IR kare anahtarı: {frame}; önceki üye: {frames[frame]}')
                frames[frame] = member
                row['frame'] = frame
                content = source.read(member)
                row['image_sha256'] = hashlib.sha256(content).hexdigest()
                if Path(member).suffix.lower() in {'.jpg', '.jpeg'} and not content.endswith(b'\xff\xd9'):
                    raise ValueError('JPEG son işareti eksik; örtük görüntü onarımı yapılmadı.')
                with Image.open(BytesIO(content)) as image:
                    if image.width*image.height > 25_000_000:
                        raise ValueError('Piksel limiti aşıldı.')
                    image.load()
                    row.update(width=image.width, height=image.height, mode=image.mode)
                    if image.size != (640, 512):
                        raise ValueError('Bilinen IR örneği için 640x512 bekleniyor; boyut farkı tanılama gerektiriyor.')
                    if image.mode not in {'L', 'RGB'} or image.getexif().get(274, 1) != 1:
                        raise ValueError('Desteklenmeyen mod veya EXIF yönü; örtük piksel/koordinat dönüşümü yok.')
                label_member = str(Path(member).with_suffix('.txt'))
                row['label_member'] = label_member
                label_users.add(label_member)
                if label_member not in source.members:
                    raise ValueError('Karşılık gelen TXT eksik; boş etiket varsayılmadı.')
                raw = source.read(label_member, limit=262144)
                row['label_sha256'] = hashlib.sha256(raw).hexdigest()
                text = raw.decode('utf-8-sig')
                boxes, issues, observed = parse_sample_labels(text, member, row['width'], row['height'])
                result['issues'].extend({'label_member': label_member, **e} for e in issues)
                row.update(boxes=boxes, person_count=sum(b['class_id'] == 0 for b in boxes),
                           observed_class_id_rows=dict(observed))
                result['source_person_annotations_parsed'] += row['person_count']
                # Kaynak parser sınır hatalarını raporlar; burada hiçbiri skorlamaya geçemez.
                normalized = [(b['class_id'], b['cx'], b['cy'], b['width_normalized'], b['height_normalized']) for b in boxes]
                if len(normalized) != len(set(normalized)):
                    raise ValueError('Tekrarlanan Person etiketi; Ultralytics dedup işlemine bırakılmadı.')
                if issues:
                    continue
                empty = not text.strip()
                if not empty and not boxes:
                    raise ValueError('Dolu TXT fakat ayrıştırılan geçerli kutu yok.')
                row.update(included=not empty, reason='empty_annotation_pending_review' if empty else 'included')
                stem = f'ir_{frame:08d}'
                image_rel = f"{'review_images' if empty else 'images/eval'}/{stem}{Path(member).suffix.lower()}"
                (output/image_rel).write_bytes(content)
                row['image_path'] = image_rel
                if empty:
                    result['empty_annotation_files'] += 1
                else:
                    # Aynı YOLO değerleri; kaynak TXT'ye dokunmadan ayrı kopya. BOM kaldırılır.
                    label_rel = f'labels/eval/{stem}.txt'
                    (output/label_rel).write_text(text, encoding='utf-8')
                    row['label_path'] = label_rel
                    row['prepared_label_sha256'] = hashlib.sha256(text.encode()).hexdigest()
            except (KeyError, *READ_ERRORS) as exc:
                result['issues'].append({'member': member, 'issue': 'IR_validation_error', 'detail': str(exc)})
            if progress and len(result['images']) % 50 == 0:
                progress(f"IR doğrulaması: {len(result['images'])}/{len(ir_images)}")
        if len(roots) != 1:
            result['issues'].append({'member': '', 'issue': 'ambiguous_or_missing_IR_root', 'roots': sorted(roots)})
        for member in source.members:
            if (Path(member).parent.as_posix() in roots and Path(member).suffix.lower() == '.txt'
                    and Path(member).name.lower() != 'count.txt' and member not in label_users):
                result['issues'].append({'member': member, 'issue': 'orphan_IR_label'})
        result['count_txt_checks'] = []
        for root in roots:
            count_member = root+'/count.txt'
            if count_member in source.members:
                try:
                    text = source.read(count_member, limit=65536).decode('utf-8-sig')
                    humans = re.search(r'number\s+of\s+humans\s*:\s*(\d+)', text, re.I)
                    images = re.search(r'number\s+of\s+images\s*:\s*(\d+)', text, re.I)
                    matches = bool(humans and images and int(humans[1]) == result['source_person_annotations_parsed'] and int(images[1]) == len(ir_images))
                    result['count_txt_checks'].append({'member': count_member, 'text': text, 'matches': matches})
                    if not matches:
                        result['issues'].append({'member': count_member, 'issue': 'IR_count_txt_mismatch'})
                except READ_ERRORS as exc:
                    result['issues'].append({'member': count_member, 'issue': 'IR_count_txt_error', 'detail': str(exc)})
    result['included_images'] = sum(r['included'] for r in result['images'])
    result['excluded_images'] = len(result['images'])-result['included_images']
    result['included_person_annotations'] = sum(r['person_count'] or 0 for r in result['images'] if r['included'])
    result['image_modes'] = dict(Counter(r['mode'] for r in result['images'] if r['mode']))
    if not result['included_images'] or not result['included_person_annotations']:
        result['issues'].append({'member': '', 'issue': 'no_scorable_IR_person_data'})
    if not result['issues']:
        result['status'] = 'ready'
    # test/val yalnızca framework okuma anahtarıdır; kaynak split oluşturulmaz.
    yaml = f'path: {json.dumps(str(output))}\ntrain: null\nval: images/eval\ntest: images/eval\nnames:\n  0: Person\n'
    (output/'evaluation.yaml').write_text(yaml, encoding='utf-8')
    return result
