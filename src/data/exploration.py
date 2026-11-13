"""Kullanıcının gözden geçirdiği split yapılandırmasını keşif raporuna dönüştürür."""
from pathlib import Path

from .annotations import load_coco, load_voc, safe_relative
from .audit import audit_split, duplicate_report


def run_exploration(root: Path, config: dict, *, hash_images: bool = False) -> tuple[dict, dict]:
    """Splitleri yeniden üretmez. Desteklenmeyen şemayı/eksik config'i açık hata ile durdurur.

    splits: {özgün_split_adı: {format: coco|voc, images: göreli_dizin,
    annotations: göreli_json_yolu|göreli_xml_dizini}}. Hatalı XML'ler ayrı kaydedilir;
    kısmi sayımlar complete=False ile işaretlenir. JSON ilişkisel hatası tüm kaynağı
    geçersiz yapar; sessizce etiket düşürülmez.
    """
    if config.get('schema_confirmed') is not True or not config.get('splits'):
        raise ValueError('Önce gerçek yapıyı inceleyip schema_confirmed ve splits ayarlayın.')
    if config.get('dataset_version') != '1.2.1':
        raise ValueError('Bu notebook HIT-UAV v1.2.1 için hazırlanmıştır.')
    root = Path(root).resolve()
    reports, loaded = {}, {}
    for split, specification in config['splits'].items():
        image_root = root / safe_relative(specification['images'])
        annotation_path = root / safe_relative(specification['annotations'])
        errors = []
        samples = []
        try:
            if specification['format'] == 'coco':
                samples = load_coco(annotation_path, bbox_format=config['bbox_format'])
            elif specification['format'] == 'voc':
                if not annotation_path.is_dir():
                    raise FileNotFoundError(annotation_path)
                paths = sorted(annotation_path.rglob('*.xml'))
                if not paths:
                    raise ValueError('Seçili dizinde XML yok.')
                for path in paths:
                    try:
                        samples.append(load_voc(path, coordinate_origin=config['coordinate_origin']))
                    except (ValueError, TypeError, OSError, KeyError, SyntaxError) as exc:
                        errors.append({'file': str(path.relative_to(root)), 'error': str(exc)})
            else:
                raise ValueError('Şema desteklenmiyor; ham dosyaya göre yeni adaptör gerekli.')
        except (ValueError, TypeError, OSError, KeyError, SyntaxError) as exc:
            errors.append({'file': str(annotation_path.relative_to(root)), 'error': str(exc)})
        report = audit_split(image_root, samples, hash_images=hash_images)
        report['annotation_errors'] = errors
        report['complete'] = not errors
        if errors:
            report['count_scope'] += ' AYRIŞTIRMA HATASI: sayımlar eksik olabilir.'
        reports[split] = report
        loaded[split] = samples
    return {'splits': reports, 'duplicates': duplicate_report(reports),
            'config': config, 'limitations': [
                'Eksik insan etiketleri yalnızca görsel incelemeyle doğrulanabilir.',
                'SHA256 kontrolü yakın kare/aynı uçuş/konum sızıntısını dışlamaz.',
                'Çözünürlük ham sıcaklık veya radyometrik kalibrasyon bilgisi değildir.',
                'DontCare eğitim ve değerlendirme politikası henüz onaylanmadı.',
            ]}, loaded
