"""Denetim sonuçlarını benzersiz çalışma klasöründe CSV/JSON/PNG olarak saklar."""
from datetime import datetime, timezone
import csv
import hashlib
from importlib.metadata import version
from io import BytesIO
import json
from pathlib import Path
import uuid
from zipfile import BadZipFile

from PIL import Image

from .annotations import Sample
from .audit import plot_sample
from .hit_uav import CLASSES, SPLITS
from .hit_uav_archive import HitUAVArchive


def _write_json(path, value):
    # NaN/Infinity üretmek yerine hata: paylaşılabilir JSON standardını korur.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def save_audit_reports(report: dict, loaded: dict, archive_path: Path, output_root: Path, *,
                       code_revision: str, samples_per_split: int = 1,
                       dataset_version='1.2.1', zenodo_record='7633134',
                       prior_md5_verified_by_user=True) -> Path:
    """Her çalıştırmada yeni dizin: eski raporların üzerine yazılmaz, ham görüntüler kopyalanmaz.

    En fazla split başına 3 kutulu örnek kaydedilir. Önce kalite JSON/CSV yazılır;
    sonraki çizim hatasında metadata status='partial' kalır. Grafikler yalnızca bu
    çalıştırmanın verilerinden hesaplanır. Geçmiş medyan 12x19 sonuç olarak yazılmaz.
    """
    if not isinstance(samples_per_split, int) or isinstance(samples_per_split, bool) or not 0 <= samples_per_split <= 3:
        raise ValueError('samples_per_split 0–3 arasında tam sayı olmalı.')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    now = datetime.now(timezone.utc)
    output = Path(output_root) / (now.strftime('run_%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    archive_path = Path(archive_path)
    metadata = {
        'status': 'partial', 'dataset': 'HIT-UAV', 'dataset_version': dataset_version,
        'version_provenance': 'Kullanıcının mevcut arşiv için bildirdiği sürüm; çevrim içi doğrulama yapılmadı.',
        'zenodo_record_id': zenodo_record, 'source_url': f'https://zenodo.org/records/{zenodo_record}',
        'analysis_date_utc': now.isoformat(), 'code_revision': code_revision,
        'archive': {'path': str(archive_path), 'bytes': archive_path.stat().st_size,
                    'mtime_ns': archive_path.stat().st_mtime_ns,
                    'prior_md5_verified_by_user': prior_md5_verified_by_user,
                    'md5_recomputed_in_this_run': False},
        'configuration': {'normal_json_root': report['normal_json_root'], 'bbox_format': 'xywh_pixels',
                          'class_mapping': CLASSES, 'samples_per_split': samples_per_split,
                          'splits_unchanged': list(SPLITS), 'image_validation':
                          {s: report['splits'][s]['image_validation'] for s in SPLITS}},
        'environment': {p: version(p) for p in ('Pillow', 'matplotlib')},
        'outputs': [],
    }
    _write_json(output / 'analysis_metadata.json', metadata)
    _write_json(output / 'data_quality.json', report)
    columns = ['split', 'image_files', 'raw_image_records', 'readable_images', 'raw_annotation_records',
               *CLASSES.values(), 'Unknown', 'accepted_boxes', 'person_median_width_px',
               'person_median_height_px', 'person_side_lt16_fraction', 'quality_issue_count']
    with (output / 'split_statistics.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for split in SPLITS:
            item = report['splits'][split]
            writer.writerow({
                'split': split, **{k: item[k] for k in ('image_files', 'raw_image_records',
                                 'readable_images', 'raw_annotation_records')},
                **item['objects_by_class_raw'],
                'accepted_boxes': sum(item['objects_by_class_accepted'].values()),
                'person_median_width_px': item['person_box_sizes']['median_width_px'],
                'person_median_height_px': item['person_box_sizes']['median_height_px'],
                'person_side_lt16_fraction': item['person_box_sizes']['at_least_one_side_lt16_fraction'],
                'quality_issue_count': len(item['issues']) + len(item['missing_images']) + len(item['unannotated_images']),
            })

    classes = [*CLASSES.values(), 'Unknown']
    fig, axis = plt.subplots(figsize=(11, 5))
    positions = list(range(len(classes)))
    for offset, split in enumerate(SPLITS):
        values = report['splits'][split]['objects_by_class_raw']
        axis.bar([x + (offset-1)*.25 for x in positions], [values[c] for c in classes],
                 width=.25, label=split, color=('#2166ac', '#b35806', '#4d9221')[offset])
    axis.set_xticks(positions, classes, rotation=15)
    axis.set(title='HIT-UAV · Ham etiket satırlarının sınıf dağılımı', xlabel='Orijinal sınıf', ylabel='Nesne/etiket satırı sayısı')
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    axis.legend(title='Özgün split')
    fig.tight_layout()
    fig.savefig(output / 'class_distribution.png', dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    all_sizes = [size for parsed in loaded.values() for size in parsed.person_sizes]
    for dimension, axis in enumerate(axes):
        maximum = max((size[dimension] for size in all_sizes), default=1)
        for index, split in enumerate(SPLITS):
            values = [size[dimension] for size in loaded[split].person_sizes]
            if values:
                axis.hist(values, bins=30, range=(0, maximum), histtype='step', linewidth=1.8,
                          label=f'{split} (n={len(values)})',
                          color=('#2166ac', '#b35806', '#4d9221')[index],
                          linestyle=('-', '--', ':')[index])
        if not all_sizes:
            axis.text(.5, .5, 'Uygun Person kutusu yok', transform=axis.transAxes, ha='center')
        axis.axvline(16, color='#444444', linestyle='--', label='16 piksel')
        axis.set(xlabel=('Genişlik' if dimension == 0 else 'Yükseklik') + ' (piksel)', ylabel='Person kutusu sayısı')
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        axis.legend(fontsize=9)
    fig.suptitle('HIT-UAV · Referansı geçerli, sonlu/pozitif ve etiket sınırları içindeki Person kutuları')
    fig.tight_layout()
    fig.savefig(output / 'person_box_sizes.png', dpi=160)
    plt.close(fig)

    sample_manifest, sample_errors = [], []
    with HitUAVArchive(archive_path) as source:
        for split in SPLITS:
            count = 0
            for sample in sorted(loaded[split].samples, key=lambda s: s.file_name):
                if count >= samples_per_split:
                    break
                if not any(box.label == 'Person' for box in sample.boxes):
                    continue
                member = source.root + split + '/' + sample.file_name
                if member not in source.members:
                    continue
                try:
                    # Yalnızca Person ve DontCare görselleştirilir; diğer sınıflar raporda korunur.
                    selected = Sample(sample.file_name, sample.width, sample.height,
                                      tuple(b for b in sample.boxes if b.label in {'Person', 'DontCare'}))
                    with source.image(member):  # Çizimden önce aynı çözme/piksel limiti uygulanır.
                        pass
                    figure = plot_sample(BytesIO(source.read(member)), selected)
                    figure.axes[0].set_title(f'{split} · {sample.file_name} · Person / kesik çizgi: DontCare')
                    name = f'sample_{split}_{count+1:02d}.png'
                    figure.savefig(output / name, dpi=140)
                    plt.close(figure)
                    sample_manifest.append({'output': name, 'split': split, 'source_member': member})
                    count += 1
                except (OSError, ValueError, BadZipFile, RuntimeError, Image.DecompressionBombError) as exc:
                    plt.close('all')
                    sample_errors.append({'split': split, 'file': sample.file_name, 'error': str(exc)})
    metadata['selected_samples'] = sample_manifest
    metadata['sample_errors'] = sample_errors
    metadata['status'] = 'complete_with_sample_errors' if sample_errors else 'complete'
    # Kalite sorunları data_quality.json içinde ayrıca raporlanır; complete veri kusursuz demek değildir.
    metadata['outputs'] = [{'file': p.name, 'bytes': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                           for p in sorted(output.iterdir()) if p.name != 'analysis_metadata.json']
    _write_json(output / 'analysis_metadata.json', metadata)
    return output
