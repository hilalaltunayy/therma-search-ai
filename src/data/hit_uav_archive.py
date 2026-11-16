"""Mevcut ZIP'ten salt okunur HIT-UAV denetimi; ağ isteği veya çıkarma yapmaz."""
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
from statistics import median
from zipfile import ZipFile, BadZipFile

from PIL import Image

from .annotations import safe_relative
from .download import inspect_zip
from .hit_uav import CLASSES, SPLITS, PREVIOUS_COUNTS, parse_hit_uav
from .inventory import IMAGE_SUFFIXES


class HitUAVArchive:
    """Sürüm kökü otomatik bulunur; birden fazla normal_json gösterimi varsa durur.

    Üye yolları, tekrarlar, symlink ve toplam açılmış boyut eski inspect_zip ile
    denetlenir. Yalnızca açılan üyeler CRC kontrolünden geçer. Tam ZIP hash kontrolü
    değildir. Bir dosya en fazla 32 MiB; tüm arşiv varsayılan en fazla 20 GiB açılmış
    içerik beyan edebilir. Dosyalar belleğe tek tek alınır, diske çıkarılmaz.
    """
    def __init__(self, path: Path, *, max_unpacked_bytes=20 * 1024**3, max_member_bytes=32 * 1024**2):
        self.path = Path(path)
        members = inspect_zip(self.path, max_unpacked_bytes=max_unpacked_bytes)
        self.members = {entry['name']: entry['bytes'] for entry in members if not entry['name'].endswith('/')}
        self.max_member_bytes = max_member_bytes
        suffix = 'normal_json/annotations/train.json'
        roots = [name[:-len(suffix)] + 'normal_json/' for name in self.members
                 if name == suffix or name.endswith('/' + suffix)]
        if len(roots) != 1:
            raise ValueError('ZIP içinde tam bir normal_json kökü seçilemedi; eksik veya birden fazla aday.')
        self.root = roots[0]
        for split in SPLITS:
            if self.root + f'annotations/{split}.json' not in self.members:
                raise ValueError(f'ZIP içinde {split}.json eksik.')
        self.archive = None

    def __enter__(self):
        self.archive = ZipFile(self.path)
        return self

    def __exit__(self, *args):
        self.archive.close()
        self.archive = None

    def read(self, member):
        """Boyut sınırı uygulanır; tüm üyenin okunması ZIP CRC doğrulamasını tetikler."""
        safe_relative(member)
        size = self.members[member]
        if size > self.max_member_bytes:
            raise ValueError(f'ZIP üyesi okuma limitini aşıyor: {member}')
        if self.archive is None:
            raise RuntimeError('Arşivi with bloğunda kullanın.')
        with self.archive.open(member) as stream:
            content = stream.read(self.max_member_bytes + 1)
        if len(content) != size or len(content) > self.max_member_bytes:
            raise ValueError('ZIP üye boyutu eşleşmiyor.')
        return content

    def image(self, member):
        """Tek görüntüyü çözer, bağımsız Pillow kopyası döndürür; piksel limiti uygular."""
        from io import BytesIO
        with Image.open(BytesIO(self.read(member))) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError('Görüntü piksel limiti aşıldı.')
            image.load()
            return image.copy()

    def image_members(self, split):
        prefix = self.root + split + '/'
        return {name[len(prefix):]: name for name in self.members
                if name.startswith(prefix) and Path(name).suffix.lower() in IMAGE_SUFFIXES}


def size_summary(sizes):
    """Pozitif/sonlu, referansı geçerli, etiket boyutuna göre sınır içi Person kutuları.

    <16 oranı: min(genişlik,yükseklik)<16 olan kutu sayısı / incelenen kutu sayısı.
    Nesne kimliği, COCO küçük nesne metriği veya model başarımı değildir.
    """
    return {'count': len(sizes),
            'median_width_px': median(w for w, _ in sizes) if sizes else None,
            'median_height_px': median(h for _, h in sizes) if sizes else None,
            'at_least_one_side_lt16_count': sum(min(w, h) < 16 for w, h in sizes),
            'at_least_one_side_lt16_fraction': sum(min(w, h) < 16 for w, h in sizes) / len(sizes) if sizes else None}


def audit_hit_uav_zip(path: Path, *, verify_images=True, expected_counts=None) -> tuple[dict, dict]:
    """Tüm splitleri mevcut ZIP'ten okur. expected_counts yalnızca karşılaştırma içindir.

    Ham annotation sayıları ve kabul edilen kutular ayrı raporlanır. Görüntü okumak
    her üyeyi tek tek çözer; Drive I/O sürebilir. verify_images=False ise bozuk dosya
    ve gerçek çözünürlük denetimi 'not_run' olur. Ortak adlar içerik hash'i değildir.
    """
    if expected_counts is None:
        expected_counts = PREVIOUS_COUNTS
    splits, loaded, names = {}, {}, {}
    with HitUAVArchive(path) as source:
        for split in SPLITS:
            label_path = source.root + f'annotations/{split}.json'
            raw = source.read(label_path)
            parsed = parse_hit_uav(json.loads(raw))
            files = source.image_members(split)
            labels = {s.file_name: s for s in parsed.samples}
            issues = list(parsed.issues)
            resolutions = Counter()
            readable = 0
            if verify_images:
                for name, member in sorted(files.items()):
                    try:
                        with source.image(member) as image:
                            size = image.size
                        readable += 1
                        resolutions[f'{size[0]}x{size[1]}'] += 1
                        sample = labels.get(name)
                        if sample and size != (sample.width, sample.height):
                            issues.append({'issue': 'dimension_mismatch', 'file': name,
                                           'image_size': list(size), 'label_size': [sample.width, sample.height]})
                        if size != (640, 512):
                            issues.append({'issue': 'unexpected_resolution', 'file': name, 'image_size': list(size)})
                        if sample:
                            for box in sample.boxes:
                                x1, y1, x2, y2 = box.xyxy
                                if x1 < 0 or y1 < 0 or x2 > size[0] or y2 > size[1]:
                                    issues.append({'issue': 'box_out_of_actual_image_bounds', 'file': name,
                                                   'label': box.label, 'xyxy': list(box.xyxy)})
                    except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
                        issues.append({'issue': 'unreadable_image', 'file': name, 'detail': str(exc)})
            accepted_counts = Counter(b.label for s in parsed.samples for b in s.boxes)
            counts = {'images': len(files), 'Person': parsed.raw_counts['Person'], 'objects': parsed.raw_annotation_records}
            comparison = {key: {'previous_user_report': value, 'recomputed': counts[key],
                                'matches': counts[key] == value}
                          for key, value in expected_counts.get(split, {}).items()}
            splits[split] = {
                'image_files': len(files), 'raw_image_records': parsed.raw_image_records,
                'accepted_image_records': len(parsed.samples), 'raw_annotation_records': parsed.raw_annotation_records,
                'objects_by_class_raw': parsed.raw_counts,
                'objects_by_class_accepted': {name: accepted_counts[name] for name in CLASSES.values()},
                'readable_images': readable if verify_images else None,
                'image_validation': 'completed' if verify_images else 'not_run', 'resolutions': dict(resolutions),
                'missing_images': sorted(set(labels) - set(files)),
                'unannotated_images': sorted(set(files) - set(labels)),
                'empty_annotation_records': [s.file_name for s in parsed.samples if not s.boxes],
                'issues': issues, 'issue_counts': dict(Counter(i['issue'] for i in issues)),
                'dimensions_from_default': parsed.dimensions_from_default,
                'person_box_sizes': size_summary(parsed.person_sizes),
                'previous_count_comparison': comparison,
                'annotation_sha256': hashlib.sha256(raw).hexdigest(),
            }
            loaded[split] = parsed
            names[split] = {'files': set(Path(n).name for n in files),
                            'labels': set(Path(n).name for n in labels)}
        overlaps = {
            f'{a}__{b}': {'image_basenames': sorted(names[a]['files'] & names[b]['files']),
                          'annotation_basenames': sorted(names[a]['labels'] & names[b]['labels'])}
            for a, b in combinations(SPLITS, 2)
        }
        report = {'splits': splits, 'normal_json_root': source.root,
                  'cross_split_filename_overlap': overlaps,
                  'person_box_sizes_all_splits': size_summary([s for p in loaded.values() for s in p.person_sizes]),
                  'limitations': [
                      'Ortak dosya adı eşit içerik kanıtı değildir; farklı adlar da sızıntıyı dışlamaz.',
                      'Yakın kare, aynı uçuş/video/konum ve yeniden kodlanmış görüntü sızıntısı denetlenmedi.',
                      'Ham sınıf sayımları geçersiz veya eksik referanslı annotation satırlarını da kapsar.',
                      'Person boyutları pozitif/sonlu, referansı geçerli ve etiket boyutuna göre sınır içi kutulardır; görüntü dosyası eksik/bozuk olabilir.',
                      'DontCare korunur; eğitim ve değerlendirme politikası belirlenmedi.',
                      'Etiketsiz nesneler ve boş kayıtların gerçek negatifliği görsel inceleme gerektirir.',
                      'ZIP CRC yalnızca okunan üyelerde kontrol edilir; önceki MD5 doğrulaması kullanıcı beyanıdır.',
                  ]}
    return report, loaded
