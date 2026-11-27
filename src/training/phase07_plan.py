"""Immutable, source-only Phase 07 plans. No torch, model loading or training on import."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from src.data.audit import file_digest
from .hit_uav_yolo import POLICY, prepare_hit_uav_yolo, validate_prepared_dataset, write_json

ARMS = {'P07-C0': {}, 'P07-A1': {'scale': .25}, 'P07-A2': {'mosaic': 0.}, 'P07-R1': {'imgsz': 960}}
# Required even when the installed library could provide a default. No silent inheritance.
TRAIN_FIELDS = '''epochs patience batch imgsz pretrained optimizer seed deterministic single_cls rect cos_lr
close_mosaic amp fraction freeze multi_scale compile lr0 lrf momentum weight_decay warmup_epochs
warmup_momentum warmup_bias_lr box cls dfl nbs hsv_h hsv_s hsv_v degrees translate scale shear
perspective flipud fliplr bgr mosaic mixup cutmix copy_paste copy_paste_mode workers cache augment
agnostic_nms iou max_det half val split time'''.split()
IO_FIELDS = {'model','data','project','name','save_dir','resume','exist_ok','save','save_period','plots','mode'}
EVALUATION = {'split':'val','native_confidence_floor':.001,'confidence':.25,'matching_iou':.5,
              'nms_iou':.7,'max_det':300,'half':False,'native_batch':1,'rect':True,
              'latency_warmup_images':5,'latency_repeats':20,
              'selection':'filtered original HIT-UAV validation native mAP50:95 only',
              'checkpoint_selection':'Ultralytics 8.3.228 native source-val fitness (mAP50:95)',
              'forbidden_selection_data':['HIT-UAV test','WiSARD','future external holdout']}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def read_baseline_evidence(run):
    """Read requested/effective settings and actual optimizer groups; reject unresolved evidence.

    PyYAML is already a transitive Ultralytics dependency, imported only for this read.
    No checkpoint is deserialized. Initial weights are hashed, never downloaded.
    """
    import yaml
    run=Path(run).resolve()
    paths={'args':run/'ultralytics/train/args.yaml','effective':run/'effective_train_arguments.json',
           'optimizer':run/'optimizer_effective.json','manifest':run/'dataset_manifest.json',
           'summary':run/'run_summary.json','initial_weights':run/'initial_weights/yolo11s.pt'}
    for path in paths.values():
        if not path.is_file(): raise FileNotFoundError(f'Required baseline evidence missing; no defaults/download: {path}')
    hashes={key:file_digest(path) for key,path in paths.items()}
    args=yaml.safe_load(paths['args'].read_text())
    effective=json.loads(paths['effective'].read_text())
    optimizer=json.loads(paths['optimizer'].read_text())
    manifest=json.loads(paths['manifest'].read_text())
    summary=json.loads(paths['summary'].read_text())
    if not isinstance(args,dict) or not isinstance(effective,dict): raise ValueError('Arguments must be mappings.')
    for key in TRAIN_FIELDS:
        if key not in args or key not in effective or (effective[key] is None and key not in ('freeze','time')): raise ValueError(f'Missing actual baseline setting: {key}')
    differences={key:[args.get(key),value] for key,value in effective.items() if key not in IO_FIELDS and args.get(key)!=value}
    allowed={'warmup_bias_lr':[.1,0.]}
    if differences and (effective['optimizer']!='auto' or differences!=allowed):
        raise ValueError(f'Unresolved requested/effective argument differences: {differences}')
    if manifest.get('status')!='ready' or manifest.get('policy')!=POLICY: raise ValueError('Baseline data policy/status mismatch.')
    if summary.get('dataset_manifest_sha256')!=hashes['manifest'] or summary.get('pretrained_sha256')!=hashes['initial_weights']:
        raise ValueError('Baseline manifest/initial-weight identity mismatch.')
    if summary.get('environment',{}).get('ultralytics')!='8.3.228': raise ValueError('Unsupported baseline Ultralytics contract.')
    if effective['task']!='detect' or effective['imgsz']!=640 or effective['amp'] is not False:
        raise ValueError('This controlled bridge requires the actual 640/FP32 detect baseline.')
    groups=optimizer.get('parameter_groups',[])
    if optimizer.get('class')!='AdamW' or len(groups)!=3: raise ValueError('Actual AdamW three-group optimizer evidence required.')
    lr=groups[0].get('initial_lr');betas=groups[0].get('betas')
    if not isinstance(lr,(int,float)) or lr<=0 or not isinstance(betas,list) or len(betas)!=2 or betas[1]!=.999:
        raise ValueError('Unsupported/missing resolved AdamW LR/betas.')
    for group in groups:
        if group.get('initial_lr')!=lr or group.get('lr')!=lr or group.get('betas')!=betas or group.get('eps')!=1e-8:
            raise ValueError('Inconsistent initial optimizer parameter groups.')
        if group.get('amsgrad') is not False or group.get('maximize') is not False:
            raise ValueError('Unsupported optimizer flags; do not substitute defaults.')
    accumulation=max(round(effective['nbs']/effective['batch']),1)
    expected_decay=effective['weight_decay']*effective['batch']*accumulation/effective['nbs']
    if [g.get('weight_decay') for g in groups]!=[0.,expected_decay,0.]: raise ValueError('Effective weight-decay groups disagree with baseline batch/nbs.')
    return {'run_directory':str(run),'hashes':hashes,'paths':{k:str(p) for k,p in paths.items()},
            'requested_args':args,'effective_args':effective,'optimizer':optimizer,'manifest':manifest,
            'environment':summary['environment'],'resolved_lr':lr,'resolved_beta1':betas[0],
            'requested_effective_differences':differences,'initial_accumulation':accumulation}


def data_identity(manifest):
    """Original train/val membership, exclusions, image/label hashes and GT; ignores temporary paths."""
    fields=('split','source_member','source_filename','image_sha256','label_sha256','disposition','reason',
            'raw_annotation_count','source_classes','width','height','person_xyxy_pixels')
    return sorted(({k:r.get(k) for k in fields} for r in manifest['images'] if r['split'] in ('train','val')),
                  key=lambda r:(r['split'],r['source_member']))


def resolve_plan(evidence, *, batch=4, git_commit):
    if type(batch) is not int or batch not in (1,2,4): raise ValueError('Use common batch 4, 2 or 1 for ALL arms; no per-arm batch override.')
    actual=evidence['effective_args']
    if actual['nbs']%batch: raise ValueError('Common batch must divide actual nbs.')
    common={k:deepcopy(v) for k,v in actual.items() if k not in IO_FIELDS}
    common.update(optimizer='AdamW',lr0=evidence['resolved_lr'],momentum=evidence['resolved_beta1'],
                  warmup_bias_lr=actual['warmup_bias_lr'],batch=batch,imgsz=640,epochs=40,patience=10,seed=42,
                  amp=False,half=False,device='0',save=True,save_period=1,resume=False,
                  exist_ok=False,plots=True,mode='train',val=True,split='val',conf=None)
    arms={}
    for name,change in ARMS.items():
        settings={**common,**change}
        skipped=bool(change) and all(common[k]==v for k,v in change.items())
        arms[name]={'status':'skipped_identical_to_control' if skipped else 'prepared_not_trained',
                    'overrides':change,'train_arguments':settings,
                    'metrics':None,'small_object_recall':None,'fp_per_image':None,'latency':None,'GPU_memory':None}
    plan={'schema_version':1,'git_commit':git_commit,'baseline_hashes':evidence['hashes'],
          'baseline_environment':evidence['environment'],'initial_weights':evidence['paths']['initial_weights'],
          'common':common,'arms':arms,'evaluation':EVALUATION,
          'policy':POLICY,'train_val_identity_sha256':fingerprint(data_identity(evidence['manifest'])),
          'nominal_accumulation':max(round(common['nbs']/batch),1),
          'accumulation_policy':'Ultralytics warmup interpolates 1 -> nbs/batch; identical sample order/count and policy across arms.',
          'bridge':'Fresh common-batch control; not a one-factor attribution comparison to historical batch=8 baseline.',
          'training_authorized':False,'training_executed':False}
    plan['plan_sha256']=fingerprint(plan)
    return plan


def validate_plan(plan):
    unsigned={k:v for k,v in plan.items() if k!='plan_sha256'}
    if fingerprint(unsigned)!=plan['plan_sha256']: raise ValueError('Frozen plan hash mismatch.')
    if set(plan['arms'])!=set(ARMS) or plan['evaluation']!=EVALUATION or plan['policy']!=POLICY:
        raise ValueError('Protocol/arms changed.')
    if plan['common']['optimizer']!='AdamW' or plan['common']['amp'] is not False: raise ValueError('Explicit common optimizer/FP32 required.')
    for name,arm in plan['arms'].items():
        if arm['train_arguments']!={**plan['common'],**ARMS[name]}: raise ValueError('Per-arm common setting drift.')
    return plan


def prepare_phase07(baseline_run, archive, output_root, work_root, *, git_commit, batch=4):
    """Preparation only. New unique block; only original train and val files are copied."""
    block=Path(output_root).resolve()/(datetime.now(timezone.utc).strftime('run_phase07_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
    block.mkdir(parents=True,exist_ok=False)
    status={'status':'preparing','training_executed':False,'memory_preflight':'pending','errors':[]}
    write_json(block/'preparation_status.json',status)
    try:
        evidence=read_baseline_evidence(baseline_run)
        if file_digest(Path(archive))!=evidence['manifest']['archive']['sha256']: raise ValueError('Source ZIP differs from actual baseline.')
        dataset=Path(work_root).resolve()/block.name/'dataset'
        _,manifest=prepare_hit_uav_yolo(archive,dataset,code_revision=git_commit,splits=('train','val'))
        if data_identity(manifest)!=data_identity(evidence['manifest']): raise ValueError('Train/val membership, labels or exclusions differ from baseline.')
        plan=resolve_plan(evidence,batch=batch,git_commit=git_commit)
        validate_plan(plan)
        write_json(block/'frozen_plan.json',plan)
        write_json(block/'dataset_manifest.json',manifest)
        write_json(block/'baseline_evidence.json',{k:v for k,v in evidence.items() if k!='manifest'})
        for name,arm in plan['arms'].items():
            directory=block/name;directory.mkdir();write_json(directory/'arm_specification.json',arm)
        status.update(status='prepared_not_trained',dataset_directory=str(dataset),plan_sha256=plan['plan_sha256'],
                      batch=batch,training_gate='disabled; explicit subsequent authorization + all-arm GPU preflight required')
        return block,status
    except Exception as exc:
        status.update(status='blocked',errors=[f'{type(exc).__name__}: {exc}'])
        raise
    finally:
        write_json(block/'preparation_status.json',status)
        preparation_report(block)


def restore_data(block, archive, work_root):
    """Rebuild temporary data after Colab interruption without changing the frozen block."""
    block=Path(block);plan=validate_plan(json.loads((block/'frozen_plan.json').read_text()))
    expected=json.loads((block/'dataset_manifest.json').read_text())
    if fingerprint(data_identity(expected))!=plan['train_val_identity_sha256']: raise ValueError('Frozen manifest identity mismatch.')
    if file_digest(Path(archive))!=expected['archive']['sha256']: raise ValueError('Source ZIP identity changed.')
    target=Path(work_root).resolve()/block.name/'dataset'
    if target.exists():
        validate_prepared_dataset(target)
        manifest=json.loads((target/'dataset_manifest.json').read_text())
    else:
        _,manifest=prepare_hit_uav_yolo(archive,target,code_revision=plan['git_commit'],splits=('train','val'))
    if data_identity(manifest)!=data_identity(expected): raise ValueError('Restored train/val data differ from frozen identity.')
    return target


def preparation_report(block):
    """Bounded human-readable readout of saved evidence; no synthetic model metrics."""
    block=Path(block);status=json.loads((block/'preparation_status.json').read_text())
    lines=['# Faz 07 — Kontrollü eğitim hazırlığı',f"Durum: {status['status']}",
           'Bu hazırlık eğitim yapmaz. GPU preflight sadece geçici modelde forward/backward bellek kontrolüdür; optimizer adımı yoktur.',
           f"Hatalar: {status['errors']}"]
    path=block/'frozen_plan.json'
    if path.is_file():
        plan=json.loads(path.read_text());common=plan['common']
        manifest=json.loads((block/'dataset_manifest.json').read_text())
        lines += [f"Plan SHA256: `{plan['plan_sha256']}` · Git: `{plan['git_commit']}`",
                  f"Ortak optimizer={common['optimizer']}, lr0={common['lr0']}, beta1={common['momentum']}, beta2=.999; "
                  f"weight_decay={common['weight_decay']}, cos_lr={common['cos_lr']}, lrf={common['lrf']}; "
                  f"batch={common['batch']}, nbs={common['nbs']}, nominal accumulation={plan['nominal_accumulation']}; "
                  f"warmup={common['warmup_epochs']} epoch, warmup_bias_lr={common['warmup_bias_lr']}; seed=42, epochs=40, patience=10, FP32.",
                  '| Kol | imgsz | scale | mosaic | Durum |','|---|---:|---:|---:|---|']
        for name,arm in plan['arms'].items():
            a=arm['train_arguments'];lines.append(f"| {name} | {a['imgsz']} | {a['scale']} | {a['mosaic']} | {arm['status']} |")
        lines += [f"Doğrulanmış kaynak train/val kapsamı: { {k:v['prepared'] for k,v in manifest['splits'].items()} }",
                  'Her aday yalnız ortak C0’dan tek faktör değiştirir. Tarihsel batch=8 baseline ile nedensel tek-faktör karşılaştırma yapılmaz.',
                  'Bellek geçişi kayıtları preflights/ altındadır. Eğitim kapısı varsayılan kapalıdır; gerçek GPU eğitimi ayrıca yetkilendirilmelidir.',
                  'Validation daha önce model seçiminde kullanıldı; splitler arası yakın-kare/sızıntı riski sürer. WiSARD zaten görülmüş tanılama verisidir. '
                  'WiSARD ve HIT-UAV test seçimden dışlanır; final saha genellemesi için yeni bağımsız dış küme gerekir.']
    (block/'preparation_report.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    return block/'preparation_report.md'
