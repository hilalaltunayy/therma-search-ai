"""Frozen HIT-UAV Person checkpoint -> WiSARD IR zero-shot external evaluation.

No training, checkpoint/dataset download, VIS decoding or threshold search.
Each call creates a new run and preserves failure diagnostics. Heavy imports
occur only after source validation; tests mock the model, not actual scores.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
import shutil
import time
import uuid

from src.data.audit import file_digest
from src.data.wisard_reports import _csv, _json
from .inference import load_person_detector, predict_person
from .person_detection import match_person_predictions
from .wisard_external_data import prepare_ir_evaluation
from .wisard_external_figures import review_contact_sheets, save_fixed_figures, save_map_curves
from .wisard_external_metrics import aggregate_fixed_records, small_object_recall

TRAINING_RUN_REFERENCE = 'run_yolo11s_20261120T151540Z_78fb2af9'
HISTORICAL_REFERENCE = {'provenance':'previous user-reported measurements, not current results',
                        'IR_images':264,'Person_annotations':1006,'empty_annotations':3}
LIMITATIONS = [
    'The MtErie sample is reported to be one flight with temporally correlated frames; image counts are not independent missions.',
    'This is a limited cross-dataset stress test, not proof of generalization across independent rescue missions.',
    'HIT-UAV and WiSARD scores are not interchangeable benchmark scores: dataset, annotation and exclusion policies differ.',
    'Empty annotations are uncertain and excluded; FP/image describes the scored subset, not verified negative scenes or full-archive false-alarm rate.',
    'Small-object recall is descriptive for explicit GT denominators in original IR pixels; no independent-frame confidence interval is inferred.',
    'Domain shift may involve scenes, capture conditions and object sizes; performance here cannot identify their causal effects.',
    'Person class 0 semantics follow the previously user-verified sample adapter; annotation completeness is not independently guaranteed.',
]


@dataclass(frozen=True)
class ExternalEvalConfig:
    imgsz: int = 640
    confidence: float = .25
    matching_iou: float = .50
    nms_iou: float = .70
    max_det: int = 300
    map_confidence_floor: float = .001

    def __post_init__(self):
        expected = (640,.25,.50,.70,300,.001)
        if tuple(asdict(self).values()) != expected:
            raise ValueError('Phase 05 protocol is fixed before WiSARD evaluation; threshold tuning is not supported.')


def environment_metadata():
    packages = {}
    for name in ('torch','torchvision','ultralytics','Pillow','matplotlib'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {'python':platform.python_version(),'platform':platform.platform(),'packages':packages,
            'cpu_processor':platform.processor() or None,'cpu_count':os.cpu_count()}


def evaluation_device():
    import torch
    gpu = torch.cuda.is_available()
    result = {'device':0 if gpu else 'cpu', 'batch':8 if gpu else 1,
              'torch_version':torch.__version__, 'cuda_version':torch.version.cuda,
              'gpu_available':gpu,'gpu_name':torch.cuda.get_device_name(0) if gpu else None}
    if gpu:
        memory = torch.cuda.get_device_properties(0).total_memory
        result['gpu_total_memory_bytes'] = memory
        if memory < 6*1024**3:
            result['batch'] = 4
    return result


def _write_tables(output, manifest, records):
    _csv(output/'exclusion_manifest.csv', [r for r in manifest['images'] if not r['included']],
         ['member','frame','reason','label_member','width','height','image_sha256','label_sha256'])
    rows = []
    for record in records:
        m = record['matching']
        small = small_object_recall(record['ground_truth_xyxy'], [p['target_index'] for p in m['matches']], sizes=record['ground_truth_sizes_px'])
        row = {'member':record['member'],'frame':record['frame'],
               'width':record['image']['width'],'height':record['image']['height'],
               'gt_person_count':len(record['ground_truth_xyxy']),
               'prediction_count':len(record['detections']), **{k:m[k] for k in ('tp','fp','fn')},
               'precision':m['tp']/(m['tp']+m['fp']) if m['tp']+m['fp'] else None,
               'recall':m['tp']/(m['tp']+m['fn']) if m['tp']+m['fn'] else None}
        for key, stats in small.items():
            row[key+'_gt'] = stats['ground_truth_count']
            row[key+'_detected'] = stats['detected_count']
            row[key+'_recall'] = stats['recall']
        rows.append(row)
    fields = ['member','frame','width','height','gt_person_count','prediction_count','tp','fp','fn','precision','recall']
    fields += [key+'_'+suffix for key in ('width_lt_16','height_lt_16','both_lt_16') for suffix in ('gt','detected','recall')]
    _csv(output/'per_image_metrics.csv',rows,fields)


def _verify_copy(data_root, manifest):
    """Check immutable image/label copies; ignore only framework .cache indices."""
    for row in manifest['images']:
        if row['included']:
            if file_digest(data_root/row['image_path']) != row['image_sha256']:
                raise ValueError('Prepared IR image changed during evaluation.')
            if file_digest(data_root/row['label_path']) != row['prepared_label_sha256']:
                raise ValueError('Prepared IR annotation changed during evaluation.')


def _report(summary, manifest, output):
    lines = ['# WiSARD IR — Zero-Shot External Evaluation',
             f"Status: **{summary['status']}** · UTC: {summary['started_utc']} · Git: `{summary['git_commit']}`",
             '## Protocol and provenance',
             f"Existing HIT-UAV-trained checkpoint; historical training run reference: `{TRAINING_RUN_REFERENCE}` (user supplied). "
             'No retraining, fine-tuning, threshold search, VIS evaluation, pairing or synchronization was performed.',
             f"Historical sample reference, not a new measurement: {HISTORICAL_REFERENCE}.",
             f"Model/dataset identities: {json.dumps(summary['input_hashes'],ensure_ascii=False)}.",
             f"Configuration: {summary['configuration']}. Device: {summary.get('runtime')}. "
             f"Environment: {summary['environment']}.",
             '## Independently measured input coverage',
             f"IR candidates: {manifest.get('source_ir_image_candidates')}; parsed Person annotations: {manifest.get('source_person_annotations_parsed')}; "
             f"empty TXT: {manifest.get('empty_annotation_files')}. Included: {manifest.get('included_images')}; excluded: {manifest.get('excluded_images')}. "
             'Input counts are only complete when input_validation_passed=true. Empty TXT is not a verified negative; identities and review sheets are saved. '
             'Malformed IR data blocks all scoring rather than silently producing a cleaned subset.',
             f"Validation issues: {json.dumps(manifest.get('issues',[]),ensure_ascii=False)}."]
    if summary['status'] == 'complete':
        fixed, maps = summary['fixed_threshold'], summary['ultralytics_map']
        lines += ['## Ultralytics mAP (separate procedure)',
                  f"mAP@50: {maps['mAP50']:.6f}; mAP@50:95: {maps['mAP50_95']:.6f}. "
                  'Native evaluation uses confidence floor .001, NMS IoU .70, max_det 300 on exactly the included IR images. '
                  'It does not use the custom TP/FP/FN matcher. Native curve-optimum P/R is not used as fixed-threshold precision/recall.',
                  '## Fixed-threshold diagnostics',
                  f"Confidence .25, matching IoU .50, NMS IoU .70, max_det 300. Precision: {fixed['precision']}; Recall: {fixed['recall']}; "
                  f"TP: {fixed['tp']}; FP: {fixed['fp']}; FN: {fixed['fn']}; FP/evaluated image: {fixed['false_positives_per_evaluated_image']}. "
                  'Matching is confidence-descending greedy, highest-IoU unmatched GT, one-to-one. Duplicate detections are FP. '
                  'No predictions makes precision undefined (null). The FP rate is conditional on the annotated scored subset; excluded empty scenes are not scored.',
                  '## Small-object recall in original image pixels',
                  '| GT size condition | Detected GT | Total GT | Missed GT | Recall |',
                  '|---|---:|---:|---:|---:|']
        for name, r in fixed['small_object_recall'].items():
            lines.append(f"| {name} | {r['detected_count']} | {r['ground_truth_count']} | {r['missed_count']} | {r['recall']} |")
        lines += ['The <16 pixel conditions are strict. Groups overlap; do not sum their denominators. '
                  'The global one-to-one matching is reused, not rerun for each size group. An empty GT group has null recall.',
                  f"Measured IR GT sizes in pixels: {fixed['ground_truth_size_pixels']}.",
                  '## Localization',
                  f"Matched TP IoU: {fixed['localization_matched_iou']}. "
                  f"Best prediction IoU for every GT: {fixed['localization_best_iou_per_gt']}. "
                  +fixed['localization_scope'],
                  '## Figures and per-image evidence',
                  'GT boxes are red; matched predictions blue; FP magenta; missed GT / FN orange dashed. '
                  'Small-person examples are selected from images with a width<16 or height<16 GT. '
                  'Confidence histograms include predictions at confidence>=.25, grouped by the custom matcher. '
                  'mAP curves are exported directly from native metric arrays, without selecting an operating threshold. '
                  'Examples are deterministic, at most four per category, spread across eligible image order; they are not a representative statistical sample. '
                  'A category without examples produces no example PNG. All generated report figures are 200 DPI.']
    else:
        lines += ['## Evaluation not completed',f"Error: {summary.get('error')}. No completed model-performance conclusion is available. "
                  'Partial files are diagnostics, not a successful real-data evaluation.']
    lines += ['## Domain shift and scientific limitations',*LIMITATIONS,
              '## Reproducibility and artifacts',
              'Model/ZIP SHA256 values are checked again at the end. Local prepared data is byte-copied, original pixels/labels and source splits are unchanged. '
              'The test/val keys in evaluation.yaml are framework aliases for the same IR evaluation subset; train is null. No new dataset split is created. '
              'Original hashes, per-member manifest, per-image metrics, predictions and metric-curve arrays are saved. '
              'Model evaluation may fuse in-memory layers; the checkpoint file is never saved or overwritten. '
              f"Duration seconds: {summary.get('duration_seconds')}. Input integrity: {summary.get('inputs_unchanged')}."]
    for p in sorted((output/'figures').glob('*.png')):
        lines.append(f'\n![{p.stem}](figures/{p.name})')
    (output/'evaluation_report.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')


def run_wisard_external_evaluation(checkpoint_path, archive_path, output_root, work_root, *, git_commit, config=None):
    """Run-all entry point. Existing local checkpoint only; actual inference or explicit failure.

    All model-performance metrics remain null unless the full evaluation succeeds.
    A unique run and diagnostic report survive missing inputs or malformed labels.
    """
    config = config or ExternalEvalConfig()
    run_id = datetime.now(timezone.utc).strftime('run_wisard_external_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8]
    output = Path(output_root).resolve()/run_id
    output.mkdir(parents=True, exist_ok=False)
    figures = output/'figures'
    figures.mkdir()
    data_root = Path(work_root).resolve()/run_id/'ir_eval'
    checkpoint_path, archive_path = Path(checkpoint_path).resolve(), Path(archive_path).resolve()
    print('WiSARD external evaluation outputs:', output)
    summary = {'status':'initializing','started_utc':datetime.now(timezone.utc).isoformat(),
               'git_commit':git_commit,'configuration':asdict(config),'environment':environment_metadata(),
               'historical_user_reference':HISTORICAL_REFERENCE,'training_run_reference':TRAINING_RUN_REFERENCE,
               'input_hashes':{},'input_validation_passed':False,'inputs_unchanged':None,
               'fixed_threshold':None,'ultralytics_map':None,'limitations':LIMITATIONS,
               'output_directory':str(output), 'local_prepared_data':str(data_root)}
    manifest = {'status':'not_validated','images':[],'issues':[]}
    records = []
    started = time.monotonic()
    try:
        for name, path in [('model',checkpoint_path),('dataset_zip',archive_path)]:
            summary['input_hashes'][name] = {'path':str(path),'exists':path.is_file(),'sha256':None}
        missing = [k for k, r in summary['input_hashes'].items() if not r['exists']]
        if missing:
            raise FileNotFoundError('Existing input required, no download attempted: '+', '.join(missing))
        for entry in summary['input_hashes'].values():
            entry['sha256'] = file_digest(Path(entry['path']))
        if checkpoint_path.suffix != '.pt':
            raise ValueError('Existing .pt Person checkpoint required.')
        summary['status'] = 'validating_IR'
        _json(output/'evaluation_summary.json',summary)
        manifest = prepare_ir_evaluation(archive_path,data_root)
        _json(output/'data_manifest.json',manifest)
        _write_tables(output,manifest,[])
        review_contact_sheets(manifest,data_root,figures)
        if manifest['status'] != 'ready':
            raise ValueError(f"Malformed/unsupported IR data: {len(manifest['issues'])} diagnostic issues; see data_manifest.json")
        summary['input_validation_passed'] = True
        summary['coverage'] = {k:manifest[k] for k in ('source_ir_image_candidates','source_person_annotations_parsed','empty_annotation_files',
                                                       'included_images','excluded_images','included_person_annotations')}
        summary['historical_reference_comparison'] = {
            key:{'historical':ref,'measured':measured,'matches':ref==measured} for key, ref, measured in [
                ('IR_images',264,manifest['source_ir_image_candidates']),('Person_annotations',1006,manifest['source_person_annotations_parsed']),
                ('empty_annotations',3,manifest['empty_annotation_files'])]}
        if summary['environment']['packages']['ultralytics'] != '8.3.228':
            raise RuntimeError('Install the pinned evaluation runtime ultralytics==8.3.228; no model/dataset is downloaded by this evaluator.')
        runtime = evaluation_device()
        summary['runtime'] = runtime
        print('Evaluation device:',runtime)
        summary['status'] = 'evaluating'
        _json(output/'evaluation_summary.json',summary)
        model = load_person_detector(checkpoint_path)
        # Existing frozen checkpoint only. No model.train(), model.save() or optimizer.
        result = model.val(data=str(data_root/'evaluation.yaml'), split='test', imgsz=config.imgsz,
                           conf=config.map_confidence_floor, iou=config.nms_iou, max_det=config.max_det,
                           device=runtime['device'], batch=runtime['batch'], half=False, workers=0,
                           plots=False, save_json=True, project=str(output),name='ultralytics_eval',exist_ok=False)
        native_gt = getattr(result,'nt_per_class',None)
        native_images = getattr(result,'nt_per_image',None)
        if native_gt is None or native_images is None:
            raise ValueError('Native evaluator GT/image denominators unavailable; no score substituted.')
        if sum(map(int,native_gt)) != manifest['included_person_annotations'] or sum(map(int,native_images)) != manifest['included_images']:
            raise ValueError('Native evaluator skipped/deduplicated data: GT/image denominators differ from the validated IR manifest.')
        maps = {'mAP50':float(result.box.map50),'mAP50_95':float(result.box.map),
                'procedure':'Ultralytics 8.3.228 independent native evaluation',
                'confidence_floor':config.map_confidence_floor,'evaluated_images':manifest['included_images'],
                'native_ground_truth_count':sum(map(int,native_gt)),'native_images_with_gt':sum(map(int,native_images))}
        if not all(math.isfinite(maps[key]) and 0 <= maps[key] <= 1 for key in ('mAP50','mAP50_95')):
            raise ValueError('Native mAP values invalid/non-finite; no score substituted.')
        curve_data = save_map_curves(result, figures)
        _json(output/'ultralytics_curves.json',curve_data)
        _json(output/'ultralytics_metrics.json',{'native_results_dict':{k:float(v) for k,v in result.results_dict.items()},
                                               'note':'Native P/R may use curve optimum; not custom fixed-threshold P/R.'})
        with (output/'predictions.jsonl').open('w',encoding='utf-8') as stream:
            for row in manifest['images']:
                if not row['included']:
                    continue
                prediction = predict_person(model,str(data_root/row['image_path']),confidence=config.confidence,
                                            imgsz=config.imgsz,device=runtime['device'])
                if prediction['image'] != {'width':row['width'],'height':row['height']}:
                    raise ValueError('Prediction/source image dimensions differ.')
                targets = [b['xyxy'] for b in row['boxes']]
                matching = match_person_predictions(targets,prediction['detections'],confidence=config.confidence,iou_threshold=config.matching_iou)
                record = {'member':row['member'],'frame':row['frame'],'image_path':row['image_path'],
                          'ground_truth_xyxy':targets,'ground_truth_sizes_px':[[b['width_px'],b['height_px']] for b in row['boxes']],
                          **prediction,'matching':matching,
                          'prediction_confidence_threshold':config.confidence}
                records.append(record)
                stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        fixed = aggregate_fixed_records(records)
        selections = save_fixed_figures(records,fixed,data_root,figures)
        _json(output/'figure_manifest.json',selections)
        _verify_copy(data_root,manifest)
        summary.update(status='complete',fixed_threshold=fixed,ultralytics_map=maps,
                       native_curves_available=curve_data['available'])
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}',fixed_threshold=None,ultralytics_map=None)
        raise
    finally:
        # Detect accidental input writes even on inference failure. Never restore/rewrite inputs.
        after = {}
        for name, entry in summary['input_hashes'].items():
            path = Path(entry['path'])
            if entry['sha256'] is not None:
                after[name] = file_digest(path) if path.is_file() else None
        summary['inputs_unchanged'] = all(after.get(k) == r['sha256'] for k,r in summary['input_hashes'].items() if r['sha256'] is not None) if after else None
        if summary['inputs_unchanged'] is False:
            summary.update(status='failed',error='Input hash changed during evaluation; scores invalidated.',fixed_threshold=None,ultralytics_map=None)
        summary['duration_seconds'] = time.monotonic()-started
        _write_tables(output,manifest,records)
        if not (output/'predictions.jsonl').exists():
            (output/'predictions.jsonl').write_text('',encoding='utf-8')
        _json(output/'data_manifest.json',manifest)
        if (data_root/'evaluation.yaml').exists():
            shutil.copy2(data_root/'evaluation.yaml',output/'evaluation.yaml')
        _json(output/'input_hashes.json',{'before':summary['input_hashes'],'after_sha256':after,'unchanged':summary['inputs_unchanged']})
        _json(output/'reproducibility.json',{'git_commit':git_commit,'configuration':asdict(config),'environment':summary['environment'],
                'runtime':summary.get('runtime'),'threshold_tuning':False,'retraining':False,'VIS_used':False,
                'score_scope':'nonempty, valid IR annotations only; original source splits unchanged'})
        _report(summary,manifest,output)
        _json(output/'evaluation_summary.json',summary)
        _json(output/'artifacts.json',[{'path':str(p.relative_to(output)),'bytes':p.stat().st_size,'sha256':file_digest(p)}
               for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'artifacts.json'])
    if summary['status'] != 'complete':
        raise RuntimeError(summary['error'])
    return output,summary
