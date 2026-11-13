"""Görüntü/etiket tutarlılığı ve bölümler arası tam kopya adayları; kaynakları değiştirmez."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

from PIL import Image

from .annotations import Sample, safe_relative
from .inventory import IMAGE_SUFFIXES

EXPECTED_LABELS = ('Person', 'Car', 'Bicycle', 'OtherVehicle', 'DontCare')


def file_digest(path: Path, algorithm: str = 'sha256') -> str:
    """Dosyayı belleğe bütünüyle almadan özetler. Eşit hash tam bayt kopyası adayıdır."""
    digest = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def audit_split(image_root: Path, samples: list[Sample], *, hash_images: bool = False) -> dict:
    """Girdi: doğrulanmış split görüntü kökü ve ayrıştırılmış etiketler.

    Çıktı: dosya envanteri, okunabilir görüntü çözünürlükleri, sınıf başına nesne ve
    görüntü sayısı, boş kayıtlar, eksik/eşleşmeyen/bozuk dosyalar ve kutu sorunları.
    'unannotated_images' kesin etiketsiz demek değildir: seçilen annotation kaynağıyla
    eşleşmez. Boş etiket geçerli negatif veya eksik anotasyon olabilir; insan inceler.
    """
    image_root = Path(image_root).resolve()
    if not image_root.is_dir():
        raise FileNotFoundError(image_root)
    paths = sorted(p for p in image_root.rglob('*')
                   if p.is_file() and not p.is_symlink() and p.suffix.lower() in IMAGE_SUFFIXES)
    files = {p.relative_to(image_root).as_posix(): p for p in paths}
    labels = {s.file_name: s for s in samples}
    if len(labels) != len(samples):
        raise ValueError('Split içinde aynı görüntü için birden fazla annotation kaydı.')
    resolutions, modes, object_counts, image_counts = Counter(), Counter(), Counter(), Counter()
    issues, hashes = [], {}
    readable = 0
    for name, path in files.items():
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()  # Yalnızca başlık okuma, bozuk piksel verisini gizleyebilir.
                width, height = image.size
                modes[image.mode] += 1
            readable += 1
            resolutions[f'{width}x{height}'] += 1
            sample = labels.get(name)
            if sample and (sample.width, sample.height) != (width, height):
                issues.append({'file': name, 'issue': 'dimension_mismatch',
                               'label_size': [sample.width, sample.height], 'image_size': [width, height]})
            if sample:
                for box in sample.boxes:
                    x1, y1, x2, y2 = box.xyxy
                    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
                        issues.append({'file': name, 'issue': 'box_out_of_bounds', 'box': box.xyxy})
            if hash_images:
                hashes[name] = file_digest(path)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            issues.append({'file': name, 'issue': 'unreadable_image', 'detail': str(exc)})
    for sample in samples:
        safe_relative(sample.file_name)
        object_counts.update(b.label for b in sample.boxes)
        image_counts.update({b.label for b in sample.boxes})
    # Sıfır, yalnızca bu seçili anotasyon kaynağında sayım yapılmışsa anlamlıdır.
    classes = sorted(set(EXPECTED_LABELS) | set(object_counts))
    return {
        'image_root': str(image_root), 'image_files': len(files), 'readable_images': readable,
        'annotation_image_records': len(samples), 'resolutions': dict(resolutions), 'modes': dict(modes),
        'objects_by_class': {k: object_counts[k] for k in classes},
        'images_by_class': {k: image_counts[k] for k in classes},
        'unexpected_classes': sorted(set(object_counts) - set(EXPECTED_LABELS)),
        'empty_annotation_records': [s.file_name for s in samples if not s.boxes],
        'missing_images': sorted(set(labels) - set(files)),
        'unannotated_images': sorted(set(files) - set(labels)),
        'issues': issues, 'hashes': hashes, 'hashing_enabled': hash_images,
        'count_scope': 'Seçili annotation kaynağının tüm ayrıştırılan kayıtları; eksik/bozuk görüntüler dahil.',
    }


def duplicate_report(reports: dict[str, dict]) -> dict:
    """Split içi ve split dışı aynı bayt içeriğini raporlar; asla split değiştirmez.

    Hash çalışmadıysa 'not_run'; yalnızca tam dosya kopyaları aranır. Yeniden
    kodlanmış, bitişik veya aynı uçuşa ait kareler için sonuç vermez.
    """
    if not reports or not all(r['hashing_enabled'] for r in reports.values()):
        return {'status': 'not_run', 'within_split': [], 'cross_split': []}
    groups = defaultdict(list)
    for split, report in reports.items():
        for name, digest in report['hashes'].items():
            groups[digest].append({'split': split, 'file': name})
    within, cross = [], []
    for members in groups.values():
        if len(members) > 1:
            (cross if len({x['split'] for x in members}) > 1 else within).append(members)
    return {'status': 'completed_exact_bytes_only', 'within_split': within, 'cross_split': cross}


def plot_sample(image_path: Path, sample: Sample):
    """Ham görüntü üzerinde xyxy kutuları çizer; kutuları kırpmaz veya etiketleri dönüştürmez."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    figure, axis = plt.subplots(figsize=(10, 7))
    with Image.open(image_path) as image:
        axis.imshow(image, cmap='gray' if image.mode != 'RGB' else None)
    for box in sample.boxes:
        x1, y1, x2, y2 = box.xyxy
        ignored = box.label == 'DontCare'
        color = '#ff8c00' if ignored else '#00ffff'
        axis.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False,
                                 edgecolor=color, linestyle='--' if ignored else '-', linewidth=1.5))
        axis.text(x1, y1, box.label, color='black', fontsize=9,
                  bbox={'facecolor': color, 'alpha': .85, 'pad': 1})
    axis.set(title=sample.file_name, xlabel='x (piksel)', ylabel='y (piksel)')
    figure.tight_layout()
    return figure
