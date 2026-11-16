"""WiSARD kaynak planı ve şema varsaymadan örnek ZIP envanteri; ağ/indirme yok."""
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

from PIL import Image

from .annotations import Box, safe_relative, to_xyxy
from .download import inspect_zip
from .inventory import IMAGE_SUFFIXES

SOURCE = {
    'name': 'WiSARD', 'url': 'https://sites.google.com/uw.edu/wisard/',
    'paper': 'WiSARD: A Labeled Visual and Thermal Image Dataset for Wilderness Search and Rescue',
    'doi': '10.1109/IROS47612.2022.9981298', 'venue': 'IROS 2022',
    'official_claims_supplied_by_user': {'visual_labeled_images': 26862, 'thermal_labeled_images': 29989,
        'synchronized_pairs': 15453, 'pairs_are_subset_of_other_collections': True,
        'full_archive_approx_GB': 40.54, 'sample_approx_MB': 971.6, 'sample_collection_flights': 1},
    'claim_scope': 'Kullanıcının doğruladığı resmî sayfa beyanları; yerel sayım değildir.',
    'version': None, 'license': {'status': 'not_verified', 'text': None,
        'next_check': 'Resmî dağıtımda lisans metni ve veri kapsamı, atıf/yeniden dağıtım koşulları okunmalı.'},
    'source_access_note': '2026-11-16: geliştirme ortamında resmî sayfa erişimi 403; lisans bağımsız doğrulanmadı.',
    'experiment_plan': [
        'Önce örnek dağıtımın sürüm/dosya kimliği, lisansı ve varsa yayıncı checksum değerini kaydet.',
        'Örnek tek uçuş beyanına sahiptir; tam veri setinin dağılımı veya bağımsız uçuş performansı genellenemez.',
        'RGB/termal eşleştirmeyi ad/sıra varsayımı yerine resmî eşleme belgesi/zaman bilgisiyle doğrula.',
        'Aynı uçuşun yakın kareleri ve eşzamanlı RGB/termal çiftleri farklı değerlendirme bölümlerine yayılmamalı.',
        'Mevcut split/flight metadata varsa incele; yeni split ve eğitim/değerlendirme kararları kullanıcı onayını bekler.',
        'HIT-UAV karşılaştırmasında sensör, perspektif, boyut, sınıf ve etiket farklarını koru; veri setlerini doğrudan birleştirme.',
    ],
}
MAX_SAMPLE_BYTES = 2 * 1024**3


def sample_candidates(directory: Path):
    """Yalnızca mevcut, adında wisard geçen ZIP'leri listeler; indirme/taşıma yapmaz."""
    root = Path(directory)
    return [{'path': str(p), 'bytes': p.stat().st_size, 'eligible_sample_size': p.stat().st_size <= MAX_SAMPLE_BYTES}
            for p in sorted(root.glob('*.zip')) if p.is_file() and 'wisard' in p.name.lower()] if root.is_dir() else []


class WisardArchive:
    """Genel örnek ZIP okuyucu: özel klasör adı veya annotation şeması kabul etmez.

    2 GiB sıkıştırılmış boyut kapısı tam 40,54 GB arşivi engeller. Üye yolu, symlink,
    tekrar ve toplam açılmış boyut (8 GiB) eski güvenli inspect_zip ile denetlenir.
    Bir üye en fazla 32 MiB, çözülen görüntü en fazla 25 milyon piksel olabilir.
    """
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.stat().st_size > MAX_SAMPLE_BYTES:
            raise ValueError('Yalnızca küçük örnek ZIP kabul edilir (en fazla 2 GiB); tam arşivi açmayın.')
        self.members = {row['name']: row['bytes'] for row in inspect_zip(self.path, max_unpacked_bytes=8*1024**3)
                        if not row['name'].endswith('/')}
        self.archive = None

    def __enter__(self):
        self.archive = ZipFile(self.path)
        return self

    def __exit__(self, *args):
        self.archive.close()
        self.archive = None

    def read(self, member, *, limit=32*1024**2):
        safe_relative(member)
        if self.members[member] > limit:
            raise ValueError(f'Üye boyut sınırını aşıyor: {member}')
        with self.archive.open(member) as stream:
            data = stream.read(limit+1)
        if len(data) != self.members[member] or len(data) > limit:
            raise ValueError('ZIP üye boyutu eşleşmedi.')
        return data

    def image(self, member):
        with Image.open(BytesIO(self.read(member))) as image:
            if image.width*image.height > 25_000_000:
                raise ValueError('Görüntü piksel limiti aşıldı.')
            image.load()
            return image.copy()


def preview_text(source, member):
    """En fazla 64 KiB önizleme; JSON anahtarları ve satırlar ipucudur, şema onayı değildir."""
    info = source.archive.getinfo(member)
    with source.archive.open(member) as stream:
        data = stream.read(65537)
    truncated = len(data) > 65536 or info.file_size > 65536
    text = data[:65536].decode('utf-8-sig', errors='replace')
    result = {'member': member, 'truncated': truncated, 'preview': text[:3000], 'format_confirmed': False}
    if Path(member).suffix.lower() == '.json' and not truncated:
        try:
            value = json.loads(text)
            result['json_type'] = type(value).__name__
            if isinstance(value, dict):
                result['json_keys'] = list(value)[:40]
        except ValueError as exc:
            result['json_error'] = str(exc)
    return result


def inspect_wisard(source):
    """Tüm aday görüntülerde gerçek boyut/mod/kanal okur; modaliteyi kanaldan tahmin etmez."""
    files, images, errors, previews, licenses = [], [], [], [], []
    for member, size in sorted(source.members.items()):
        path = Path(member)
        files.append({'member': member, 'bytes': size, 'extension': path.suffix.lower(), 'parent': str(path.parent)})
        if path.suffix.lower() in IMAGE_SUFFIXES:
            row = {'member': member, 'width': None, 'height': None, 'mode': '', 'bands': '', 'channels': None, 'status': 'unreadable'}
            try:
                with source.image(member) as image:
                    row.update(width=image.width, height=image.height, mode=image.mode,
                               bands=','.join(image.getbands()), channels=len(image.getbands()), status='ok')
            except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
                errors.append({'member': member, 'error': str(exc)})
            images.append(row)
        is_license_candidate = path.name.lower().startswith(('license', 'copying', 'notice', 'readme'))
        if (is_license_candidate and len(licenses) < 10) or (path.suffix.lower() in {'.json', '.xml', '.txt', '.csv', '.yaml', '.yml'} and len(previews) < 12):
            try:
                result = preview_text(source, member)
                (licenses if is_license_candidate else previews).append(result)
            except (OSError, ValueError, BadZipFile, RuntimeError) as exc:
                errors.append({'member': member, 'error': str(exc)})
    # Sadece gözlenen tokenlar; ne klasör ne dosya adı gerçek flight/split kanıtı sayılır.
    hints = [{'member': row['member'], 'parent': row['parent'],
              'split_name_tokens': '/'.join(p for p in Path(row['member']).parts[:-1] if p.lower() in {'train','val','validation','test'}),
              'flight_name_tokens': '/'.join(p for p in Path(row['member']).parts[:-1] if re.search(r'flight|sequence|session', p, re.I)),
              'status': 'unverified_path_hint'} for row in files]
    return {'files': files, 'images': images, 'errors': errors, 'label_previews': previews,
            'license_candidates': licenses, 'context_hints': hints,
            'extensions': dict(Counter(r['extension'] for r in files)),
            'directories': dict(Counter(r['parent'] for r in files))}


@dataclass(frozen=True)
class PairingSpec:
    confirmed: bool = False
    rgb_regex: str | None = None
    thermal_regex: str | None = None
    evidence: str = ''


def match_pairs(image_members, spec: PairingSpec):
    """Doğrulanan regex'lerde key grubu ile eşleştirir; yinelenen anahtarı asla seçmez.

    İsteğe bağlı flight/split regex grupları yalnızca path token hipotezi olarak
    raporlanır. Eşleşme geometrik hizalama/zaman senkronizasyonu kanıtı değildir.
    """
    if not spec.confirmed:
        return {'status': 'not_configured', 'pairs': [], 'issues': [], 'unmatched': [], 'context_rows': []}
    if not spec.evidence.strip() or not spec.rgb_regex or not spec.thermal_regex:
        raise ValueError('Eşleştirme için gerçek örnek/kaynak kanıtı ve iki regex gerekli.')
    patterns = {side: re.compile(pattern) for side, pattern in [('rgb', spec.rgb_regex), ('thermal', spec.thermal_regex)]}
    if any('key' not in pattern.groupindex for pattern in patterns.values()):
        raise ValueError('Her iki regex key adlı grup içermeli.')
    maps, issues, context, unmatched = {'rgb': {}, 'thermal': {}}, [], [], []
    for member in sorted(image_members):
        matches = {side: pattern.fullmatch(member) for side, pattern in patterns.items()}
        found = [(side, match) for side, match in matches.items() if match]
        if len(found) != 1:
            (issues if found else unmatched).append({'member': member, 'issue': 'ambiguous_modality' if found else 'no_rule_match'})
            continue
        side, match = found[0]
        key = match.group('key')
        if not key:
            issues.append({'member': member, 'issue': 'empty_pair_key'})
            continue
        maps[side].setdefault(key, []).append(member)
        context.append({'member': member, 'modality_by_user_rule': side,
                        'flight_token': match.groupdict().get('flight') or '',
                        'split_token': match.groupdict().get('split') or '', 'status': 'unverified_path_tokens'})
    pairs = []
    for key in sorted(set(maps['rgb']) | set(maps['thermal'])):
        rgb, thermal = maps['rgb'].get(key, []), maps['thermal'].get(key, [])
        if len(rgb) == len(thermal) == 1:
            pairs.append({'key': key, 'rgb_member': rgb[0], 'thermal_member': thermal[0]})
        else:
            issues.append({'key': key, 'issue': 'missing_or_duplicate_pair_key', 'rgb': rgb, 'thermal': thermal})
    if not context:
        issues.append({'issue': 'no_images_match_pair_rules'})
    return {'status': 'matched_by_user_confirmed_rule', 'evidence': spec.evidence,
            'pairs': pairs, 'issues': issues, 'unmatched': unmatched, 'context_rows': context}


@dataclass(frozen=True)
class LabelSpec:
    confirmed: bool = False
    format: str | None = None
    image_regex: str | None = None
    label_template: str | None = None
    class_names: dict = field(default_factory=dict)
    person_class_ids: tuple = ()
    evidence: str = ''


def parse_yolo_text(text, width, height, spec):
    """Yalnızca onaylı 5 sütunlu class,cx,cy,w,h normalize TXT -> piksel xyxy.

    OBB/polygon/segmentation satırları reddedilir; kırpma, sınıf eşleme veya etiket
    yazımı yapılmaz. Format adının açık seçilmesi ve sınıf sözlüğü zorunludur.
    """
    if not spec.confirmed or spec.format != 'yolo_cxcywh_normalized':
        raise ValueError('Desteklenmeyen veya doğrulanmamış etiket formatı.')
    import math
    boxes, issues = [], []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            tokens = line.split()
            if len(tokens) != 5:
                raise ValueError('Tam 5 sütun gerekli; farklı temsil otomatik dönüştürülmez.')
            category = int(tokens[0])
            if category not in spec.class_names:
                raise ValueError('Sınıf ID sözlükte yok.')
            cx, cy, w, h = map(float, tokens[1:])
            if not all(math.isfinite(v) and 0 <= v <= 1 for v in (cx, cy, w, h)) or w <= 0 or h <= 0:
                raise ValueError('Sonlu normalize merkez/boyut ve pozitif alan gerekli.')
            xyxy = to_xyxy((cx*width, cy*height, w*width, h*height), 'cxcywh')
            box = Box(spec.class_names[category], xyxy)
            boxes.append((category, box))
            if xyxy[0] < 0 or xyxy[1] < 0 or xyxy[2] > width or xyxy[3] > height:
                issues.append({'line': index, 'issue': 'box_out_of_bounds'})
        except (ValueError, TypeError, OverflowError) as exc:
            issues.append({'line': index, 'issue': 'invalid_label_row', 'detail': str(exc)})
    return boxes, issues


def inspect_labels(source, images, spec: LabelSpec):
    if not spec.confirmed:
        return {'status': 'not_configured', 'boxes': {}, 'class_counts': {}, 'issues': [], 'matched_images': 0, 'empty_label_files': []}
    if (spec.format != 'yolo_cxcywh_normalized' or not spec.evidence.strip() or not spec.image_regex
            or not spec.label_template or not spec.class_names):
        raise ValueError('Format, kaynak kanıtı, görüntü regex/etiket template ve sınıf sözlüğü doğrulanmalı.')
    if any(type(k) is not int or k < 0 or not isinstance(v, str) or not v for k, v in spec.class_names.items()):
        raise ValueError('Sınıf sözlüğü: negatif olmayan tam sayı ID ve ad gerekli.')
    if any(type(k) is not int or k not in spec.class_names for k in spec.person_class_ids):
        raise ValueError('Person IDleri doğrulanan sınıf sözlüğünde bulunmalı.')
    pattern = re.compile(spec.image_regex)
    boxes, counts, issues, empty, matched = {}, Counter(), [], [], 0
    label_users = {}
    for image in images:
        match = pattern.fullmatch(image['member'])
        if not match:
            continue
        matched += 1
        try:
            label = safe_relative(spec.label_template.format(**match.groupdict()))
            if label in label_users:
                raise ValueError('Aynı etiket birden fazla görüntüye eşlendi; RGB/termal kopya sayımını önleyin.')
            label_users[label] = image['member']
            if image['status'] != 'ok':
                raise ValueError('Görüntü okunamadı; piksel dönüşümü yapılmadı.')
            text = source.read(label, limit=262144).decode('utf-8-sig')
            parsed, row_issues = parse_yolo_text(text, image['width'], image['height'], spec)
            boxes[image['member']] = parsed
            counts.update(box.label for _, box in parsed)
            issues.extend({'member': label, **issue} for issue in row_issues)
            if not text.strip():
                empty.append(label)
        except (KeyError, ValueError, OSError, BadZipFile, RuntimeError) as exc:
            issues.append({'member': image['member'], 'issue': 'label_mapping_or_read_error', 'detail': str(exc)})
    if not matched:
        issues.append({'issue': 'no_images_match_label_rule'})
    return {'status': 'inspected_user_confirmed_format', 'boxes': boxes, 'class_counts': dict(counts),
            'issues': issues, 'matched_images': matched, 'empty_label_files': empty}
