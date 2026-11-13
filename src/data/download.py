"""Yalnızca kullanıcı tarafından çağrılan Zenodo yardımcıları; import ağ isteği yapmaz.

Yalnızca ZIP çıkarılır. Arşiv üye yolları, CRC ve açılmış boyut limiti denetlenir.
Bu modül veri kaynağının lisansını kullanıcı adına kabul etmez.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import stat
from urllib.parse import urlparse
from urllib.request import urlopen
from zipfile import ZipFile

from .annotations import safe_relative
from .audit import file_digest


def zenodo_metadata(record_id: str, *, expected_version: str = '1.2.1') -> dict:
    """Sabit bir Zenodo kaydının küçük metadata JSON'unu alır; arşiv indirmez.

    Kullanıcı resmî sayfadan v1.2.1 kayıt ID'sini seçer. Concept DOI veya latest
    yönlendirmesi üzerinden farklı sürümle sessizce devam edilmez.
    """
    if not str(record_id).isdigit():
        raise ValueError('Resmî sayfadan sayısal Zenodo record ID girin.')
    with urlopen(f'https://zenodo.org/api/records/{record_id}', timeout=30) as response:
        data = json.load(response)
    if str(data['id']) != str(record_id) or data['metadata'].get('version') not in {expected_version, 'v' + expected_version}:
        raise ValueError('İstenen sabit kayıt/sürüm doğrulanamadı.')
    if 'HIT-UAV' not in data['metadata'].get('title', '').upper():
        raise ValueError('Kayıt başlığı HIT-UAV değil.')
    if not data['metadata'].get('license') or not data.get('files'):
        raise ValueError('Lisans veya dosya listesi eksik; indirme engellendi.')
    return data


def download_zenodo_file(metadata: dict, file_key: str, destination: Path, *,
                         approved: bool = False, max_bytes: int) -> dict:
    """Seçilen tek dosyayı boyut ve Zenodo checksum doğrulamasıyla indirir.

    Girdi: gözden geçirilmiş metadata, tam dosya anahtarı, boş hedef ve açık onay.
    Çıktı: kaynak, sürüm, lisans, checksum ve yerel SHA256 içeren manifest.
    .part dosyası hatada silinir; mevcut dosyalar üzerine yazılmaz.
    """
    if not approved:
        raise PermissionError('İndirme için kullanıcının açık onayı gerekli.')
    if max_bytes <= 0:
        raise ValueError('Boyut limiti pozitif olmalı.')
    # Metadata diskte değiştirilmiş olsa da sürüm/kaynak kontrolünü tekrar uygula.
    version = metadata['metadata'].get('version')
    if version not in {'1.2.1', 'v1.2.1'} or 'HIT-UAV' not in metadata['metadata'].get('title', '').upper():
        raise ValueError('HIT-UAV v1.2.1 metadata gerekli.')
    entry = next(f for f in metadata['files'] if f['key'] == file_key)
    size = int(entry['size'])
    if size <= 0 or size > max_bytes:
        raise ValueError('Dosya boyutu kullanıcı limitini aşıyor veya geçersiz.')
    algorithm, expected = entry['checksum'].split(':', 1)
    if algorithm not in {'md5', 'sha256'} or not expected:
        raise ValueError('Desteklenen yayıncı checksum değeri yok.')
    url = entry['links']['self']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'zenodo.org':
        raise ValueError('Yalnızca resmî Zenodo dosya bağlantısı kabul edilir.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = destination.with_suffix(destination.suffix + '.manifest.json')
    temporary = destination.with_suffix(destination.suffix + '.part')
    if destination.exists() or temporary.exists() or manifest_path.exists():
        raise FileExistsError('Hedef, geçici dosya veya manifest zaten mevcut.')
    total = 0
    try:
        with urlopen(url, timeout=60) as response, temporary.open('xb') as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                total += len(chunk)
                if total > min(size, max_bytes):
                    raise ValueError('İndirilen boyut beklenen limiti aşıyor.')
                output.write(chunk)
        if total != size or file_digest(temporary, algorithm) != expected:
            raise ValueError('Dosya boyutu veya checksum eşleşmedi.')
        manifest = {
            'dataset': 'HIT-UAV', 'version': version, 'record_id': metadata['id'],
            'doi': metadata.get('doi'), 'license': metadata['metadata']['license'],
            'source_url': url, 'file_key': file_key, 'size': total,
            'publisher_checksum': entry['checksum'], 'sha256': file_digest(temporary),
            'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        }
        temporary.rename(destination)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def inspect_zip(path: Path, *, max_unpacked_bytes: int) -> list[dict]:
    """ZIP içeriğini çıkarmadan listeler, yolları/bağlantıları ve açılmış boyutu denetler."""
    with ZipFile(path) as archive:
        infos = archive.infolist()
        names = []
        for info in infos:
            names.append(safe_relative(info.filename.rstrip('/')))
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Arşivde sembolik bağlantı var.')
        if len(names) != len(set(names)):
            raise ValueError('Arşivde tekrarlanan üye yolları var.')
        if sum(i.file_size for i in infos) > max_unpacked_bytes:
            raise ValueError('Açılmış arşiv boyutu limiti aşıyor.')
        return [{'name': i.filename, 'bytes': i.file_size} for i in infos]


def extract_zip(path: Path, destination: Path, *, approved: bool = False,
                max_unpacked_bytes: int) -> None:
    """Kullanıcı onaylı ZIP'i yeni dizine çıkarır. CRC hatasında kısmi hedef silinir."""
    if not approved:
        raise PermissionError('Arşiv açma onayı gerekli.')
    inspect_zip(path, max_unpacked_bytes=max_unpacked_bytes)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f'ZIP CRC kontrolü başarısız: {bad}')
            archive.extractall(destination)
    except Exception:
        shutil.rmtree(destination)
        raise
