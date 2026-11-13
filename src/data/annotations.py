"""Açıkça seçilen kutu konvansiyonlarını ortak piksel xyxy biçimine dönüştürür.

Bu modül HIT-UAV arşivinin COCO/VOC olduğunu iddia etmez. Ham örnek ve resmî
şema incelendikten sonra uygun adaptör ve bbox_format seçilmelidir.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class Box:
    """Sınıf adı ve sürekli piksel koordinatlarında (sol, üst, sağ, alt) kutu."""
    label: str
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class Sample:
    """Görüntüye göreli yol, etiket boyutu ve orijinal sınıf adlarıyla kutular."""
    file_name: str
    width: int
    height: int
    boxes: tuple[Box, ...]


def safe_relative(name: str) -> str:
    """Arşiv/etiket içindeki yolların veri kökü dışına çıkmasını engeller."""
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Güvensiz göreli yol: {name!r}')
    return path.as_posix()


def to_xyxy(values, bbox_format: str) -> tuple[float, float, float, float]:
    """Girdi: 4 sayı; xywh=sol/üst/genişlik/yükseklik, cxcywh=merkez tabanlı.

    Çıktı: piksel xyxy. Normalize YOLO ve açılı kutular desteklenmez;
    5 değerli kutuyu sessizce 4 değere kesmek bilimsel hata yaratır.
    """
    if len(values) != 4:
        raise ValueError('Standart kutu tam 4 koordinat içermeli; OBB ayrı adaptör ister.')
    a, b, c, d = map(float, values)
    if not all(math.isfinite(x) for x in (a, b, c, d)):
        raise ValueError('Koordinatlar sonlu olmalı.')
    if bbox_format == 'xywh':
        result = (a, b, a + c, b + d)
    elif bbox_format == 'cxcywh':
        result = (a - c / 2, b - d / 2, a + c / 2, b + d / 2)
    elif bbox_format == 'xyxy':
        result = (a, b, c, d)
    else:
        raise ValueError(f'Desteklenmeyen bbox_format: {bbox_format}')
    if result[2] <= result[0] or result[3] <= result[1]:
        raise ValueError('Kutu alanı pozitif olmalı.')
    return result


def _positive_int(value) -> int:
    number = int(value)
    if isinstance(value, bool) or number <= 0 or number != float(value):
        raise ValueError('Görüntü boyutu pozitif tam sayı olmalı.')
    return number


def load_coco(path: Path, *, bbox_format: str) -> list[Sample]:
    """Girdi: images/categories/annotations listeli JSON; biçim çağıran tarafından seçilir.

    Çıktı: annotations içermeyen görüntüler de korunarak Sample listesi.
    Tekrarlanan ID/yol, kopuk foreign key ve bozuk kutu hata üretir; veri düzeltilmez.
    COCO standardı xywh kullanır; HIT-UAV için bunu doğrulamadan seçmeyin.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    categories, images, annotations = (data[key] for key in ('categories', 'images', 'annotations'))
    classes = {row['id']: row['name'] for row in categories}
    if len(classes) != len(categories) or any(not isinstance(n, str) or not n for n in classes.values()):
        raise ValueError('Geçersiz/tekrarlanan kategori.')
    image_map = {row['id']: row for row in images}
    if len(image_map) != len(images):
        raise ValueError('Tekrarlanan görüntü ID.')
    names = [safe_relative(row['file_name']) for row in images]
    if len(set(names)) != len(names):
        raise ValueError('Tekrarlanan görüntü yolu.')
    boxes = {key: [] for key in image_map}
    seen = set()
    for ann in annotations:
        if ann['id'] in seen:
            raise ValueError('Tekrarlanan annotation ID.')
        seen.add(ann['id'])
        if ann['image_id'] not in boxes or ann['category_id'] not in classes:
            raise ValueError('Etiket bilinmeyen image/category ID içeriyor.')
        boxes[ann['image_id']].append(Box(classes[ann['category_id']], to_xyxy(ann['bbox'], bbox_format)))
    return [Sample(safe_relative(row['file_name']), _positive_int(row['width']),
                   _positive_int(row['height']), tuple(boxes[row['id']])) for row in images]


def load_voc(path: Path, *, coordinate_origin: str) -> Sample:
    """VOC XML xmin/ymin/xmax/ymax -> sürekli 0 tabanlı xyxy.

    zero_half_open: değerler aynen; one_inclusive: xmin/ymin'den 1 çıkarılır,
    xmax/ymax korunur. Konvansiyon kaynak üzerinden doğrulanmalıdır.
    Döndürülmüş veya merkez tabanlı XML sessizce VOC kabul edilmez.
    """
    if coordinate_origin not in {'zero_half_open', 'one_inclusive'}:
        raise ValueError('XML koordinat konvansiyonu açıkça seçilmeli.')
    root = ET.parse(path).getroot()
    boxes = []
    for obj in root.findall('object'):
        node = obj.find('bndbox')
        if node is None or obj.find('robndbox') is not None:
            raise ValueError('Standart VOC bndbox bekleniyor; şemayı inceleyin.')
        values = [float(node.findtext(key)) for key in ('xmin', 'ymin', 'xmax', 'ymax')]
        if coordinate_origin == 'one_inclusive':
            values[0] -= 1
            values[1] -= 1
        label = obj.findtext('name')
        if not label:
            raise ValueError('Sınıf adı eksik.')
        boxes.append(Box(label, to_xyxy(values, 'xyxy')))
    return Sample(safe_relative(root.findtext('filename') or ''),
                  _positive_int(root.findtext('size/width')),
                  _positive_int(root.findtext('size/height')), tuple(boxes))
