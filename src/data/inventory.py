"""Gerçek dosyaları okur; klasör adlarından veri seti şeması türetmez."""
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}


def inventory(root: Path) -> dict:
    """Girdi: mevcut kök dizin. Çıktı: tüm dosya uzantıları, görüntü ve etiket aday yolları.

    XML/JSON/TXT dosyaları yalnızca adaydır; README veya split listesi de olabilir.
    Symlink dosyaları izlenmez; aynı görüntünün farklı gösterimleri birleştirilmez.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f'Veri kökü bulunamadı: {root}')
    files = sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink())
    return {
        'extensions': dict(Counter(p.suffix.lower() for p in files)),
        'images': [p.relative_to(root).as_posix() for p in files if p.suffix.lower() in IMAGE_SUFFIXES],
        'label_candidates': [p.relative_to(root).as_posix() for p in files if p.suffix.lower() in {'.xml', '.json', '.txt'}],
        'directories': sorted({p.parent.relative_to(root).as_posix() for p in files}),
    }


def preview_label(path: Path) -> dict:
    """Etiket adayı için şema ipuçları verir; biçimi veya koordinatları otomatik seçmez."""
    path = Path(path)
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {'type': type(data).__name__, 'sample': str(data)[:2000]}
        return {key: {'type': type(value).__name__,
                      'sample': value[:1] if isinstance(value, list) else str(value)[:500]}
                for key, value in data.items()}
    if path.suffix.lower() == '.xml':
        root = ET.parse(path).getroot()
        return {'root_tag': root.tag, 'sample': ET.tostring(root, encoding='unicode')[:2500]}
    return {'sample': path.read_text(encoding='utf-8')[:2500]}
