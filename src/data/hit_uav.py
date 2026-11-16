"""Kullanıcının Colab'da doğruladığı HIT-UAV v1.2.1 JSON adaptörü.

Girdi: images[].filename ve annotation[]; bbox=[xmin,ymin,w,h] piksel.
Çıktı: mevcut Sample/Box nesneleri (0 tabanlı xyxy), ham sayımlar ve hata listesi.
Geçersiz satırlar raporlanır; kaynak değiştirilmez, DontCare korunur.
"""
from collections import Counter
from dataclasses import dataclass
import math

from .annotations import Box, Sample, safe_relative, to_xyxy, _positive_int

CLASSES = {0: 'Person', 1: 'Car', 2: 'Bicycle', 3: 'OtherVehicle', 4: 'DontCare'}
SPLITS = ('train', 'val', 'test')
# Kullanıcının önceki Colab ölçümleri: yalnızca karşılaştırma referansı, sonuç değildir.
PREVIOUS_COUNTS = {
    'train': {'images': 2029, 'Person': 8533, 'objects': 17628},
    'val': {'images': 290, 'Person': 1168, 'objects': 2460},
    'test': {'images': 579, 'Person': 2611, 'objects': 4811},
}


@dataclass
class ParsedLabels:
    samples: list[Sample]
    issues: list[dict]
    raw_image_records: int
    raw_annotation_records: int
    raw_counts: dict
    person_sizes: list[tuple[float, float]]
    dimensions_from_default: int


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_hit_uav(data: dict, *, expected_size=(640, 512)) -> ParsedLabels:
    """Şema hatasında durur; satır hatalarını indeks/ID ile raporlayıp diğerlerini inceler.

    Ham sayımlar tüm annotation satırlarını kapsar (bilinmeyen sınıflar ayrı).
    person_sizes yalnızca bilinen görüntüye bağlı, pozitif/sonlu ve etiket boyutuna
    göre sınır içindeki Person kutularını kapsar. Boyut alanı yoksa kullanıcının
    doğruladığı expected_size kullanılır ve kaç kayıtta kullanıldığı raporlanır.
    """
    if not isinstance(data, dict) or not isinstance(data.get('images'), list) or not isinstance(data.get('annotation'), list):
        raise ValueError('HIT-UAV JSON için images ve annotation listeleri gerekli.')
    issues = []
    def issue(kind, **detail):
        issues.append({'issue': kind, **detail})

    if 'categories' in data:
        categories = data['categories']
        if not isinstance(categories, list):
            issue('invalid_categories')
        else:
            ids = []
            for index, row in enumerate(categories):
                if (not isinstance(row, dict) or not _integer(row.get('id'))
                        or CLASSES.get(row['id']) != row.get('name')):
                    issue('category_mapping_mismatch', row=index)
                else:
                    ids.append(row['id'])
            if len(ids) != len(set(ids)):
                issue('duplicate_category_id')

    images, annotations = data['images'], data['annotation']
    id_counts = Counter(r['id'] for r in images if isinstance(r, dict) and _integer(r.get('id')))
    name_counts = Counter(r['filename'] for r in images
                          if isinstance(r, dict) and isinstance(r.get('filename'), str))
    accepted = {}
    defaults = 0
    for index, row in enumerate(images):
        try:
            if not isinstance(row, dict) or not _integer(row.get('id')):
                raise ValueError('Görüntü ID tam sayı olmalı.')
            if id_counts[row['id']] > 1:
                raise ValueError('Tekrarlanan görüntü ID.')
            name = safe_relative(row['filename'])
            if name_counts[row['filename']] > 1:
                raise ValueError('Tekrarlanan görüntü dosya adı.')
            width = _positive_int(row.get('width', expected_size[0]))
            height = _positive_int(row.get('height', expected_size[1]))
            defaults += int('width' not in row or 'height' not in row)
            accepted[row['id']] = (name, width, height)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            issue('invalid_image_record', row=index, detail=str(exc))

    ann_ids = Counter(r['id'] for r in annotations if isinstance(r, dict) and _integer(r.get('id')))
    boxes = {key: [] for key in accepted}
    raw_counts, sizes = Counter(), []
    for index, row in enumerate(annotations):
        if not isinstance(row, dict):
            issue('invalid_annotation_record', row=index)
            raw_counts['Unknown'] += 1
            continue
        category_id = row.get('category_id')
        label = CLASSES.get(category_id) if _integer(category_id) else None
        raw_counts[label or 'Unknown'] += 1
        problems = []
        if 'id' in row and (not _integer(row['id']) or ann_ids[row['id']] > 1):
            problems.append('invalid_or_duplicate_annotation_id')
        if label is None:
            problems.append('unknown_category_id')
        image_id = row.get('image_id')
        if not _integer(image_id) or image_id not in accepted:
            problems.append('missing_image_reference')
        try:
            coordinates = to_xyxy(row['bbox'], 'xywh')
            if not all(math.isfinite(value) for value in coordinates):
                raise ValueError('Koordinat dönüşümünde taşma.')
        except (KeyError, TypeError, ValueError, OverflowError):
            problems.append('invalid_bbox')
        for problem in problems:
            issue(problem, row=index)
        if problems:
            continue
        name, width, height = accepted[image_id]
        boxes[image_id].append(Box(label, coordinates))
        x1, y1, x2, y2 = coordinates
        if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
            issue('box_out_of_bounds', row=index, file=name, xyxy=list(coordinates))
        elif label == 'Person':
            sizes.append((x2-x1, y2-y1))
    samples = [Sample(name, width, height, tuple(boxes[key]))
               for key, (name, width, height) in accepted.items()]
    return ParsedLabels(samples, issues, len(images), len(annotations),
                        {name: raw_counts[name] for name in (*CLASSES.values(), 'Unknown')}, sizes, defaults)
