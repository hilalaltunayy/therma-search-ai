"""Colab GPU exploratory baseline: dönüşüm kapısı -> train/val -> best -> ayrı test.

Ultralytics ve torch lazy import edilir. Bu modülü/testleri import etmek eğitim
veya ağırlık indirmesi başlatmaz. Varsayılanlar testten önce sabittir.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import time
import uuid

from src.data.audit import file_digest
from src.evaluation.inference import predict_person
from src.evaluation.person_detection import match_person_predictions, save_comparison
from .hit_uav_yolo import prepare_hit_uav_yolo, validate_prepared_dataset, write_json, RISKS


@dataclass(frozen=True)
class BaselineConfig:
    model: str = 'yolo11s.pt'
    imgsz: int = 640
    epochs: int = 40
    batch: int = 8
    patience: int = 10
    seed: int = 42
    confidence: float = .25  # Test tanılama eşiği; testten optimize edilmez.
    match_iou: float = .5
    nms_iou: float = .7
    max_det: int = 300

    def __post_init__(self):
        if self.model != 'yolo11s.pt':
            raise ValueError('Bu baseline yalnızca yolo11s.pt içindir.')
        for name in ('imgsz', 'epochs', 'batch', 'patience', 'max_det'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f'{name} pozitif tam sayı olmalı.')
        if type(self.seed) is not int or self.seed < 0 or not 0 <= self.confidence <= 1 or not 0 < self.match_iou <= 1:
            raise ValueError('seed/confidence/match_iou geçersiz.')
        if self.nms_iou != .7 or self.max_det != 300:
            raise ValueError('Inference sözleşmesiyle aynı NMS=.7 ve max_det=300 kullanılmalı.')


def require_gpu(torch_module=None):
    """GPU yoksa model/dönüşüm/uzun CPU eğitimi başlamadan açık hata."""
    if torch_module is None:
        import torch as torch_module
    if not torch_module.cuda.is_available():
        raise RuntimeError('Colab CUDA GPU bulunamadı. Çalışma zamanı → Çalışma zamanı türünü değiştir → GPU seçin; CPU eğitimi başlatılmadı.')
    prop = torch_module.cuda.get_device_properties(0)
    return {'device': 0, 'name': prop.name, 'total_memory_bytes': prop.total_memory,
            'torch_version': torch_module.__version__, 'cuda_version': torch_module.version.cuda,
            'cudnn_version': torch_module.backends.cudnn.version()}


def choose_batch(config, gpu):
    """Küçük GPU’da varsayılan 8 -> 4; açık sayı/gerekçe kaydı. Gizli OOM retry yok."""
    small = gpu['total_memory_bytes'] < 6*1024**3
    effective = min(config.batch, 4) if small else config.batch
    return effective, {'requested': config.batch, 'effective': effective,
                       'reason': 'GPU belleği <6 GiB; önceden tanımlı güvenli azaltma' if effective != config.batch else 'İstenen batch kullanıldı',
                       'free_memory_not_guaranteed': True}


def save_loss_plot(csv_path, output):
    import matplotlib.pyplot as plt
    with Path(csv_path).open() as stream:
        rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(stream)]
    if not rows:
        raise ValueError('Eğitim results.csv boş; loss grafiği üretilemedi.')
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    try:
        for name, ax in zip(('box_loss', 'cls_loss', 'dfl_loss'), axes):
            for split in ('train', 'val'):
                key = f'{split}/{name}'
                if key not in rows[0]:
                    raise ValueError(f'Eğitim loss alanı eksik: {key}')
                ax.plot([float(r['epoch']) for r in rows], [float(r[key]) for r in rows], marker='.', label=split)
            ax.set(title=name, xlabel='Epoch', ylabel='Loss')
            ax.legend()
        fig.tight_layout()
        fig.savefig(output/'training_validation_losses.png', dpi=200)
    finally:
        plt.close(fig)


def fixed_threshold_test(model, dataset_root, manifest, output, config, *, device=0):
    """Tüm filtrelenmiş test örnekleri; önceden sabit conf/IoU ile P/R ve FP/FN.

    mAP bu işlevde hesaplanmaz. Ultralytics test val() mAP’inden ayrı sabit eşik
    tanılamasıdır; test PR eğrisinden confidence seçilmez.
    """
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=False)
    totals = {'tp': 0, 'fp': 0, 'fn': 0}
    examples, fp_rows, fn_rows, rows = [], [], [], []
    with (output/'test_predictions.jsonl').open('w', encoding='utf-8') as stream:
        for row in manifest['images']:
            if row['split'] != 'test' or row['disposition'] != 'included':
                continue
            path = Path(dataset_root)/row['image_path']
            result = predict_person(model, str(path), confidence=config.confidence, imgsz=config.imgsz, device=device)
            diagnostic = match_person_predictions(row['person_xyxy_pixels'], result['detections'],
                                                   confidence=config.confidence, iou_threshold=config.match_iou)
            for key in totals:
                totals[key] += diagnostic[key]
            record = {'source_filename': row['source_filename'], 'image_path': row['image_path'],
                      **result, 'ground_truth_xyxy': row['person_xyxy_pixels'], 'diagnostic': diagnostic}
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')
            rows.append({'source_filename': row['source_filename'], **{k: diagnostic[k] for k in totals}})
            # Örnekler yalnızca sunum içindir; tüm test metriklerine tüm görüntüler girer.
            if len(examples) < 4:
                examples.append(record)
            if diagnostic['fp'] and len(fp_rows) < 4:
                fp_rows.append(record)
            if diagnostic['fn'] and len(fn_rows) < 4:
                fn_rows.append(record)
    for category, records in [('comparison', examples), ('false_positive', fp_rows), ('false_negative', fn_rows)]:
        for i, r in enumerate(records, 1):
            save_comparison(Path(dataset_root)/r['image_path'], r['ground_truth_xyxy'], r['detections'], r['diagnostic'], output/f'{category}_{i:02d}.png')
    tp, fp, fn = (totals[k] for k in ('tp', 'fp', 'fn'))
    metrics = {**totals, 'precision': tp/(tp+fp) if tp+fp else None,
               'recall': tp/(tp+fn) if tp+fn else None, 'images': len(rows),
               'confidence_threshold': config.confidence, 'match_iou_threshold': config.match_iou,
               'nms_iou': config.nms_iou, 'max_det': config.max_det,
               'false_positive_images': sum(r['fp'] > 0 for r in rows),
               'false_negative_images': sum(r['fn'] > 0 for r in rows),
               'matching': 'Confidence-descending greedy, best unmatched GT IoU; single Person class.',
               'no_prediction_precision': 'null (undefined), not zero', 'test_threshold_tuning': False}
    write_json(output/'fixed_threshold_metrics.json', metrics)
    with (output/'per_image_errors.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['source_filename','tp','fp','fn'])
        writer.writeheader()
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(6, 5))
    try:
        ax.imshow([[tp, fp], [fn, 0]], cmap='Blues')
        for x, y, label in [(0,0,str(tp)), (1,0,str(fp)), (0,1,str(fn)), (1,1,'N/A')]:
            ax.text(x, y, label, ha='center', va='center', color='red')
        ax.set_xticks([0,1], ['Person', 'Background'])
        ax.set_yticks([0,1], ['Person', 'Background'])
        ax.set(xlabel='Ground truth', ylabel='Prediction', title=f'Fixed-threshold test confusion | conf={config.confidence}, IoU={config.match_iou}')
        fig.tight_layout()
        fig.savefig(output/'fixed_threshold_confusion_matrix.png', dpi=200)
    finally:
        plt.close(fig)
    return metrics


def _snapshot_dataset(dataset_root, run):
    """Başarılı veya başarısız hazırlığın tanılama kayıtlarını Drive’a korur."""
    for name in ('dataset_manifest.json', 'image_dispositions.csv', 'data.yaml'):
        path = dataset_root/name
        if path.exists():
            shutil.copy2(path, run/name)


def run_baseline(archive_path, output_root, work_root, *, code_revision, config=None):
    """Kullanıcı tarafından yetkilendirilen Colab eğitimi. Yerel test gerçek eğitim yapmaz.

    Eğitim yalnızca train ve val kullanır. Ayrı YOLO(best.pt).val(split='test')
    eğitim bittikten sonra bir kez çalışır. Test kayıpları/ölçümleri ayar seçmez.
    """
    config = config or BaselineConfig()
    gpu = require_gpu()
    # Kurulum sürümü sabitlenir; yanlış API ile sessiz çalışmaya devam etme.
    if version('ultralytics') != '8.3.228':
        raise RuntimeError('Notebook 04 için ultralytics==8.3.228 kurulmalı.')
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    # Eğitim metriklerini üçüncü taraf entegrasyonlarına göndermeden yerel/Drive kaydet.
    SETTINGS.update({'wandb': False, 'comet': False, 'mlflow': False, 'neptune': False,
                     'clearml': False, 'tensorboard': False, 'hub': False, 'sync': False,
                     'dvc': False, 'raytune': False})
    run_id = datetime.now(timezone.utc).strftime('run_yolo11s_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8]
    run = Path(output_root).resolve()/run_id
    run.mkdir(parents=True, exist_ok=False)
    print('Çalışma çıktıları (Drive):', run)
    dataset_root = Path(work_root).resolve()/run_id/'dataset'
    batch, batch_decision = choose_batch(config, gpu)
    summary = {'status': 'preparing_data', 'run_id': run_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
               'code_revision': code_revision, 'requested_configuration': asdict(config), 'batch_decision': batch_decision,
               'gpu': gpu, 'environment': {p: version(p) for p in ('ultralytics','torch','torchvision','Pillow','matplotlib')},
               'python': platform.python_version(), 'risks': RISKS, 'test_used_for_selection': False,
               'data_root_local': str(dataset_root), 'output_directory': str(run)}
    write_json(run/'run_summary.json', summary)
    started = time.monotonic()
    try:
        try:
            _, manifest = prepare_hit_uav_yolo(archive_path, dataset_root, code_revision=code_revision)
        finally:
            _snapshot_dataset(dataset_root, run)
        validate_prepared_dataset(dataset_root)
        summary['dataset_manifest_sha256'] = file_digest(run/'dataset_manifest.json')
        summary['data_validation'] = 'passed'
        summary['status'] = 'training'
        write_json(run/'run_summary.json', summary)
        pretrained_dir = run/'initial_weights'
        pretrained_dir.mkdir()
        # Ultralytics bilinen release asset’ini bu ayrı yola indirir. Veri indirilmez.
        model = YOLO(str(pretrained_dir/config.model), task='detect')
        summary['pretrained_sha256'] = file_digest(pretrained_dir/config.model)
        train_args = dict(data=str(dataset_root/'data.yaml'), imgsz=config.imgsz, epochs=config.epochs,
                          batch=batch, patience=config.patience, seed=config.seed, device=0,
                          pretrained=True, deterministic=True, workers=2, cache=False, amp=False,
                          project=str(run/'ultralytics'), name='train', exist_ok=False,
                          val=True, plots=True, save=True, save_period=-1, resume=False)
        summary['train_arguments'] = train_args
        write_json(run/'run_summary.json', summary)
        train_started = time.monotonic()
        def persist_effective_arguments(trainer):
            write_json(run/'effective_train_arguments.json', vars(trainer.args))
            write_json(run/'optimizer_effective.json', {
                'class': type(trainer.optimizer).__name__,
                'parameter_groups': [{k: v for k, v in group.items() if k != 'params'}
                                     for group in trainer.optimizer.param_groups]})
        model.add_callback('on_train_start', persist_effective_arguments)
        model.train(**train_args)
        summary['training_seconds'] = time.monotonic()-train_started
        train_dir = Path(model.trainer.save_dir)
        # Efektif optimizer/lr/augmentasyonlar trainer args ve args.yaml/results.csv içindedir.
        write_json(run/'effective_train_arguments.json', vars(model.trainer.args))
        best = train_dir/'weights/best.pt'
        if not best.is_file():
            raise RuntimeError('Eğitim best.pt üretmedi; test çalıştırılmadı.')
        shutil.copy2(best, run/'best.pt')
        summary['best_weights_sha256'] = file_digest(run/'best.pt')
        save_loss_plot(train_dir/'results.csv', run)
        if file_digest(dataset_root/'dataset_manifest.json') != summary['dataset_manifest_sha256']:
            raise ValueError('Veri manifesti eğitim sırasında değişti; test durduruldu.')
        validate_prepared_dataset(dataset_root)  # Eğitim sırasında kaynak kopya değiştiyse test durur.
        summary['status'] = 'evaluating_test'
        write_json(run/'run_summary.json', summary)
        best_model = YOLO(str(run/'best.pt'), task='detect')
        if best_model.names != {0: 'Person'}:
            raise ValueError('best.pt sınıf sözlüğü Person tek sınıf değil.')
        evaluation_started = time.monotonic()
        test = best_model.val(data=str(dataset_root/'data.yaml'), split='test', imgsz=config.imgsz,
                             batch=batch, device=0, conf=.001, iou=config.nms_iou, max_det=config.max_det,
                             plots=True, save_json=True, project=str(run/'ultralytics'), name='test', exist_ok=False)
        summary['test_map'] = {'mAP50': float(test.box.map50), 'mAP50_95': float(test.box.map),
                               'confidence_floor': .001, 'nms_iou': config.nms_iou, 'max_det': config.max_det,
                               'framework': 'Ultralytics 8.3.228', 'scope': 'filtered original test subset'}
        # Native P/R eğri optimumu operasyonel eşik değildir, başlık metriği olarak kullanılmaz.
        write_json(run/'ultralytics_test_metrics.json', {k: float(v) for k, v in test.results_dict.items()})
        summary['test_fixed_threshold'] = fixed_threshold_test(best_model, dataset_root, manifest,
                                                               run/'test_diagnostics', config)
        summary['test_evaluation_seconds'] = time.monotonic()-evaluation_started
        summary['status'] = 'complete_exploratory_baseline'
        _write_report(run, summary, manifest)
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        (run/'training_report.md').write_text('# Exploratory baseline tamamlanmadı\n\n'+summary['error']+'\n\nKısmi çıktılar korunmuştur; bu çalışma başarılı eğitim/değerlendirme sonucu değildir.\n'+'\n'.join(RISKS), encoding='utf-8')
        raise
    finally:
        summary['total_seconds'] = time.monotonic()-started
        write_json(run/'run_summary.json', summary)
        # Tamamlanmış/başarısız run dosyaları: ağırlıklar dahil SHA; kaynak Git’e alınmaz.
        write_json(run/'artifacts.json', [{'path': str(p.relative_to(run)), 'bytes': p.stat().st_size,
                    'sha256': file_digest(p)} for p in sorted(run.rglob('*')) if p.is_file() and p.name != 'artifacts.json'])
    return run, summary


def _write_report(run, summary, manifest):
    fixed, maps = summary['test_fixed_threshold'], summary['test_map']
    lines = ['# HIT-UAV YOLO11s — exploratory baseline',
             f"Kod: `{summary['code_revision']}` · GPU: {summary['gpu']['name']} · Seed: {summary['requested_configuration']['seed']}",
             '## Veri kapsamı ve politika',
             'Özgün split üyeliği korunmuştur; sıfır ham anotasyonlu ve DontCare içeren görüntüler bütün splitlerden dışlanmıştır. '
             'Diğer sınıf kutuları Person hedefinden çıkarılmıştır. Bu görüntülerde Person etiketlerinin tamlığı varsayılır. '
             'Standart YOLO’ya desteklenmeyen ignore maskesi verilmemiştir. Test, özgün test kümesinin filtrelenmiş alt kümesidir.',
             '| Split | Kaynak görüntü | Hazırlanan görüntü | Person | Arka plan | Dışlanan görüntüler | Dışlanan Person |',
             '|---|---:|---:|---:|---:|---|---|']
    for split, r in manifest['splits'].items():
        c = r['prepared']
        lines.append(f"| {split} | {r['source_images']} | {c['images']} | {c['Person']} | {c['person_background_images']} | {r['excluded_images_by_reason']} | {r['excluded_person_boxes_by_reason']} |")
    lines += ['## Eğitim ve seçim',
              f"İstenen ayarlar: {summary['requested_configuration']}. Batch kararı: {summary['batch_decision']}. "
              f"Eğitim süresi: {summary['training_seconds']:.1f} saniye. "
              'Best checkpoint ve erken durdurma yalnızca validation metrikleriyle seçilmiştir. Test hiperparametre/eşik seçimi için kullanılmamıştır. '
              'Tüm efektif parametreler args.yaml/effective_train_arguments.json, train/val metrik ve loss değerleri results.csv içindedir.',
              '## Ayrı test değerlendirmesi',
              f"mAP@0.50: {maps['mAP50']:.6f}; mAP@0.50:0.95: {maps['mAP50_95']:.6f}. "
              'Ultralytics mAP değerlendirmesi conf tabanı=.001, NMS IoU=.7 ve max_det=300 ile yapılmıştır.',
              f"Sabit confidence={fixed['confidence_threshold']}, eşleme IoU={fixed['match_iou_threshold']}: "
              f"Precision={fixed['precision']}, Recall={fixed['recall']}; TP={fixed['tp']}, FP={fixed['fp']}, FN={fixed['fn']}. "
              'Tahmin yoksa Precision tanımsızdır (null). Bu P/R confidence azalan sırada bire bir IoU eşlemesine dayanır. '
              'Ultralytics’in native P/R değerleri test eğrisindeki optimum eşiğe bağlı olabilir; bunlar operasyonel eşik veya başlık P/R metriği olarak kullanılmamıştır.',
              f"FP içeren görüntü: {fixed['false_positive_images']}; FN içeren görüntü: {fixed['false_negative_images']}. "
              'Örnek yoksa ilgili kategori için görsel üretilmez; sıfır hata uydurulmaz. Bütün test tahminleri JSONL olarak kaydedilir.',
              '## Sızıntı ve sınırlılıklar', *RISKS,
              f"Bu çalıştırmada hazırlanan kopyalarda split dışı byte-eşit grup sayısı: {len(manifest['cross_split_exact_byte_groups'])}. "
              'Bu bulgu yakın kare/sahne/uçuş örtüşmesinin kapsamını belirlemez. Bağımsız saha genellemesi iddiası yapılmaz.',
              '## Çıktılar',
              'best.pt, run_summary.json, dataset_manifest.json, image_dispositions.csv, artifacts.json ve ultralytics/train ile ultralytics/test altındaki sonuçlar Drive’da korunur. '
              'Checkpoint’ler yalnızca güvenilen yerel kaynaktan yüklenmelidir. Model ağırlıkları GitHub’a gönderilmez.',
              '\n![Train/validation losses](training_validation_losses.png)',
              '\n![Fixed-threshold confusion matrix](test_diagnostics/fixed_threshold_confusion_matrix.png)']
    for p in sorted((run/'ultralytics/test').glob('*.png')):
        lines.append(f'\n![{p.stem}]({p.relative_to(run)})')
    for p in sorted((run/'test_diagnostics').glob('comparison_*.png')):
        lines.append(f'\n![{p.stem}]({p.relative_to(run)})')
    for pattern in ('false_positive_*.png', 'false_negative_*.png'):
        for p in sorted((run/'test_diagnostics').glob(pattern)):
            lines.append(f'\n![{p.stem}]({p.relative_to(run)})')
    (run/'training_report.md').write_text('\n\n'.join(lines)+'\n', encoding='utf-8')
