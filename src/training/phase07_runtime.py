"""Guarded Phase 07 GPU feasibility, isolated attempts and validation-only evaluation.

Default notebook execution prepares/probes only. Training requires explicit opt-in.
No source test or WiSARD loader, automatic batch retry, checkpoint or dataset download.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import shutil
import time
import uuid

from src.data.audit import file_digest
from src.evaluation.inference import load_person_detector, predict_person
from src.evaluation.person_detection import match_person_predictions
from src.evaluation.wisard_external import environment_metadata
from src.evaluation.wisard_external_metrics import aggregate_fixed_records
from .baseline import require_gpu
from .hit_uav_yolo import validate_prepared_dataset, write_json
from .phase07_plan import validate_plan, fingerprint, data_identity


def unique_directory(parent, prefix):
    path=Path(parent)/(datetime.now(timezone.utc).strftime(prefix+'_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
    path.mkdir(parents=True,exist_ok=False)
    return path


def load_block(block, dataset):
    block=Path(block).resolve();dataset=Path(dataset).resolve()
    plan=validate_plan(json.loads((block/'frozen_plan.json').read_text()))
    validate_prepared_dataset(dataset)
    manifest=json.loads((dataset/'dataset_manifest.json').read_text())
    if manifest.get('selected_splits')!=['train','val'] or fingerprint(data_identity(manifest))!=plan['train_val_identity_sha256']:
        raise ValueError('Only frozen original train/val data are allowed; no test split.')
    if file_digest(Path(plan['initial_weights']))!=plan['baseline_hashes']['initial_weights']: raise ValueError('Initial weights changed.')
    return block,dataset,plan,manifest


def runtime_identity():
    gpu=require_gpu()
    environment=environment_metadata()
    if environment['packages']['ultralytics']!='8.3.228': raise RuntimeError('ultralytics==8.3.228 required.')
    return {'gpu':gpu,'environment':environment}


def optimizer_snapshot(trainer):
    return {'class':type(trainer.optimizer).__name__,
            'parameter_groups':[{k:v for k,v in g.items() if k!='params'} for g in trainer.optimizer.param_groups],
            'accumulate':trainer.accumulate,'scheduler':type(trainer.scheduler).__name__}


def verify_optimizer(snapshot, plan):
    expected=plan['common'];groups=snapshot['parameter_groups']
    if snapshot['class']!='AdamW' or len(groups)!=3 or snapshot['scheduler']!='LambdaLR': raise ValueError('Runtime optimizer/scheduler drift.')
    decay=expected['weight_decay']*expected['batch']*plan['nominal_accumulation']/expected['nbs']
    for g,d in zip(groups,(0.,decay,0.)):
        if g.get('initial_lr')!=expected['lr0'] or list(g.get('betas',[]))!=[expected['momentum'],.999] or g.get('eps')!=1e-8 or g.get('weight_decay')!=d:
            raise ValueError('Runtime LR/betas/epsilon/decay differ from frozen plan.')
    if snapshot['accumulate']!=plan['nominal_accumulation']: raise ValueError('Runtime nominal accumulation drift.')


def controlled_trainer_class(destination, settings, data_yaml):
    """Lazy pinned-version adapter. Resume writes to a NEW attempt, never checkpoint's old project.

    Native resume restores optimizer/EMA/scheduler epoch. We also carry best and stopper
    metadata. Ultralytics stores EMA + FP16 optimizer state: resume is not bitwise exact.
    """
    from ultralytics.models.yolo.detect import DetectionTrainer
    from ultralytics.utils import SETTINGS
    SETTINGS.update({k:False for k in ('wandb','comet','mlflow','neptune','clearml','tensorboard','hub','sync','dvc','raytune')})
    destination=Path(destination)
    class ControlledTrainer(DetectionTrainer):
        def check_resume(self, overrides):
            super().check_resume(overrides)
            # check_resume can replace all args from the old checkpoint. Route IO first,
            # then verify every frozen setting before the constructor writes args.yaml.
            self.args.data=str(data_yaml)
            self.args.project=str(destination.parent);self.args.name=destination.name
            self.args.save_dir=str(destination);self.args.exist_ok=False
            self.args.device='0'
            for key,value in settings.items():
                if key in ('resume','exist_ok'): continue
                if getattr(self.args,key,None)!=value: raise ValueError(f'Resume/effective argument drift: {key}')
        def auto_batch(self, *args, **kwargs):
            raise RuntimeError('Automatic batch adjustment forbidden; prepare a new common block.')
    return ControlledTrainer


def _trainer(destination, data, plan, arm, *, resume=None):
    settings=plan['arms'][arm]['train_arguments']
    cls=controlled_trainer_class(destination,settings,data/'data.yaml')
    return cls(overrides={**settings,'data':str(data/'data.yaml'),
                         'model':str(resume or plan['initial_weights']),
                         'resume':str(resume) if resume else False,
                         'project':str(destination.parent),'name':destination.name,'exist_ok':False})


def probe_training_memory(destination, data, plan, arm):
    """Two real train batches: forward/loss/backward, no optimizer.step or persistent weight update.

    Reserve AdamW's two state buffers explicitly. Also forward a square 2*batch
    synthetic tensor in eval mode to cover native trainer-validation batch policy.
    Bounded sample feasibility, not a proof for every augmentation/GT distribution.
    """
    import torch
    torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
    free,total=torch.cuda.mem_get_info()
    trainer=None;batch=None;loss=None;states=[];image=None
    try:
        trainer=_trainer(destination,data,plan,arm)
        trainer._setup_train()  # pinned private API: data/model/optimizer, not the train loop
        verify_optimizer(optimizer_snapshot(trainer),plan)
        for group in trainer.optimizer.param_groups:
            for p in group['params']:
                states.extend((torch.zeros_like(p),torch.zeros_like(p)))
        trainer.model.train()
        iterator=iter(trainer.train_loader)
        sampled=[]
        for _ in range(2):
            batch=trainer.preprocess_batch(next(iterator))
            sampled.extend(batch.get('im_file',[]))
            loss,_=trainer.model(batch)
            loss.sum().backward()
            trainer.model.zero_grad(set_to_none=True)
        trainer.model.eval()
        with torch.inference_mode():
            size=plan['arms'][arm]['train_arguments']['imgsz']
            image=torch.zeros((plan['common']['batch']*2,3,size,size),device='cuda',dtype=torch.float32)
            trainer.model(image)
        torch.cuda.synchronize()
        reserved=torch.cuda.max_memory_reserved()
        return {'passed':reserved<=.8*free,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                'peak_reserved_bytes':reserved,'free_bytes_at_start':free,'total_bytes':total,
                'headroom_fraction_required':.20,'sampled_train_images':sampled,
                'optimizer_steps':0,'training_executed':False,'arm':arm,'imgsz':size,
                'scope':'2 real augmented train batches + reserved AdamW state + synthetic 2*batch validation forward; no guarantee for full run.'}
    except torch.cuda.OutOfMemoryError:
        return {'passed':False,'reason':'CUDA OOM; no per-arm batch retry','arm':arm,'optimizer_steps':0,'training_executed':False}
    finally:
        del trainer,batch,loss,states,image
        gc.collect();torch.cuda.empty_cache()


def memory_preflight(block, dataset, *, probe=None):
    block,data,plan,_=load_block(block,dataset)
    out=unique_directory(block/'preflights','probe')
    record={'status':'pending','plan_sha256':plan['plan_sha256'],'training_executed':False,'results':[]}
    try:
        if any(block.glob('*/active.lock')) or (block/'active.lock').exists():
            raise RuntimeError('An active/stale training lock exists; inspect before GPU preflight.')
        record['runtime']=runtime_identity()
        lock=block/'runtime_lock.json'
        if lock.exists() and json.loads(lock.read_text())!=record['runtime']:
            raise RuntimeError('GPU/software changed within the controlled block; create a new common block.')
        if not lock.exists():
            with lock.open('x') as stream: json.dump(record['runtime'],stream,indent=2)
        for arm,spec in plan['arms'].items():
            if spec['status']=='skipped_identical_to_control': continue
            directory=out/arm
            record['results'].append((probe or probe_training_memory)(directory,data,plan,arm))
            write_json(out/'memory_preflight.json',record)
        load_block(block,data)  # Recheck input weights/data after bounded model use.
        record['status']='passed' if all(r['passed'] for r in record['results']) else 'blocked_common_batch'
        if record['status']!='passed':
            record['action']='Create a NEW block at a smaller shared batch for ALL arms and re-probe 640/960. No isolated arm retry.'
    except Exception as exc:
        record.update(status='blocked',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        write_json(out/'memory_preflight.json',record)
    return out,record


def verify_preflight(block, plan, preflight, runtime):
    path=Path(preflight).resolve()/'memory_preflight.json'
    if not path.is_relative_to(Path(block).resolve()/'preflights'): raise ValueError('Preflight must belong to this block.')
    record=json.loads(path.read_text())
    if json.loads((Path(block)/'runtime_lock.json').read_text())!=runtime: raise ValueError('Frozen block runtime mismatch.')
    expected={k for k,v in plan['arms'].items() if v['status']!='skipped_identical_to_control'}
    if record.get('status')!='passed' or record.get('plan_sha256')!=plan['plan_sha256'] or record.get('runtime')!=runtime:
        raise ValueError('Missing successful all-arm GPU preflight or runtime changed; re-probe whole block.')
    if {r['arm'] for r in record['results'] if r['passed']}!=expected: raise ValueError('Incomplete memory coverage.')


@contextmanager
def arm_lock(arm_directory):
    """Single writer. Stale locks require explicit inspection/removal, never automatic takeover."""
    path=Path(arm_directory)/'active.lock'
    with path.open('x') as stream: stream.write(datetime.now(timezone.utc).isoformat())
    try: yield
    finally: path.unlink()


def seal_snapshot(destination, files, metadata):
    """Exclusive snapshot + hashes; complete.json is written last. Partial copies never resume."""
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    hashes={}
    for name,source in files.items():
        shutil.copy2(source,destination/name);hashes[name]=file_digest(destination/name)
    write_json(destination/'complete.json',{**metadata,'files':hashes})
    return destination


def validate_snapshot(snapshot, plan, arm):
    snapshot=Path(snapshot).resolve()
    marker=json.loads((snapshot/'complete.json').read_text())
    if marker.get('plan_sha256')!=plan['plan_sha256'] or marker.get('arm')!=arm: raise ValueError('Resume snapshot belongs to a different frozen plan/arm.')
    if 'last.pt' not in marker['files'] or 'best.pt' not in marker['files'] or 'stopper.json' not in marker['files']: raise ValueError('Incomplete resume snapshot.')
    for name,digest in marker['files'].items():
        if Path(name).name!=name or file_digest(snapshot/name)!=digest: raise ValueError('Snapshot file hash mismatch.')
    return marker


def evaluate_arm(best, dataset, manifest, out, *, imgsz):
    """Frozen original val only. Native mAP and fixed assignment remain separate."""
    import statistics
    import torch
    model=load_person_detector(best)
    native=model.val(data=str(dataset/'data.yaml'),split='val',imgsz=imgsz,conf=.001,iou=.7,max_det=300,
                     batch=1,device=0,half=False,workers=0,cache=False,rect=True,plots=True,save_json=True,
                     project=str(out),name='native_val',exist_ok=False)
    rows=[r for r in manifest['images'] if r['split']=='val' and r['disposition']=='included']
    gt=sum(len(r['person_xyxy_pixels']) for r in rows)
    if sum(map(int,native.nt_per_class))!=gt or sum(map(int,native.nt_per_image))!=sum(bool(r['person_xyxy_pixels']) for r in rows):
        raise ValueError('Native validation GT denominators disagree.')
    records=[]
    with (out/'val_predictions.jsonl').open('x') as stream:
        for row in rows:
            prediction=predict_person(model,str(dataset/row['image_path']),imgsz=imgsz,device=0,confidence=.25)
            if prediction['image']!={'width':row['width'],'height':row['height']}: raise ValueError('Image size drift.')
            matching=match_person_predictions(row['person_xyxy_pixels'],prediction['detections'],confidence=.25,iou_threshold=.5)
            result={'member':row['source_member'],'ground_truth_xyxy':row['person_xyxy_pixels'],**prediction,'matching':matching}
            stream.write(json.dumps(result,allow_nan=False)+'\n');records.append(result)
    # Single-image end-to-end wall time includes decode, preprocessing, NMS and host transfer.
    paths=[str(dataset/r['image_path']) for r in rows]
    for i in range(5): predict_person(model,paths[i%len(paths)],imgsz=imgsz,device=0)
    samples=[]
    for i in range(20):
        torch.cuda.synchronize();start=time.perf_counter()
        predict_person(model,paths[i%len(paths)],imgsz=imgsz,device=0)
        torch.cuda.synchronize();samples.append(1000*(time.perf_counter()-start))
    import csv
    with (out/'per_image_metrics.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['member','tp','fp','fn']);writer.writeheader()
        writer.writerows({'member':r['member'],**{k:r['matching'][k] for k in ('tp','fp','fn')}} for r in records)
    return {'native':{'mAP50':float(native.box.map50),'mAP50_95':float(native.box.map)},
            'fixed':aggregate_fixed_records(records),'latency':{'unit':'ms/image','batch':1,'imgsz':imgsz,'samples':samples,
            'mean':statistics.mean(samples),'median':statistics.median(samples),'warmup':5,
            'scope':'20 deterministic source-val images with wraparound if needed; end-to-end, CUDA synchronized; not pure network latency.'}}


def run_arm(block, dataset, arm, preflight, *, training_authorized=False, resume_snapshot=None):
    """Future authorized execution only; each call writes a unique attempt and immutable epoch snapshots."""
    if not training_authorized: raise PermissionError('Training disabled: explicit subsequent user authorization is required.')
    block,data,plan,manifest=load_block(block,dataset)
    if arm not in plan['arms'] or plan['arms'][arm]['status']=='skipped_identical_to_control': raise ValueError('Unknown/skipped arm.')
    for candidate_arm in plan['arms']: resume_candidate(block,candidate_arm,plan)
    runtime=runtime_identity();verify_preflight(block,plan,preflight,runtime)
    snapshot=None
    if resume_snapshot:
        snapshot=Path(resume_snapshot).resolve()
        if not snapshot.is_relative_to(block/arm/'attempts'): raise ValueError('Resume must come from this arm/block.')
        validate_snapshot(snapshot,plan,arm)
    with arm_lock(block/arm):
        attempt=unique_directory(block/arm/'attempts','attempt')
        status={'status':'initializing','arm':arm,'plan_sha256':plan['plan_sha256'],'runtime':runtime,
                'resume_snapshot':str(snapshot) if snapshot else None,'metrics':None}
        write_json(attempt/'attempt_status.json',status)
        started=time.monotonic()
        try:
            import torch
            torch.cuda.reset_peak_memory_stats()
            checkpoint=None
            if snapshot:
                (attempt/'resume_input').mkdir()
                checkpoint=attempt/'resume_input/last.pt';shutil.copy2(snapshot/'last.pt',checkpoint)
                (attempt/'train/weights').mkdir(parents=True)
                shutil.copy2(snapshot/'best.pt',attempt/'train/weights/best.pt')
            trainer=_trainer(attempt/'train',data,plan,arm,resume=checkpoint)
            def verify(t):
                audit=optimizer_snapshot(t);verify_optimizer(audit,plan)
                write_json(attempt/'optimizer_effective.json',audit)
                write_json(attempt/'effective_train_arguments.json',vars(t.args))
                if snapshot:
                    t.stopper.__dict__.update(json.loads((snapshot/'stopper.json').read_text()))
            def save(t):
                write_json(attempt/'stopper.json',t.stopper.__dict__)
                files={'last.pt':t.last,'best.pt':t.best,'stopper.json':attempt/'stopper.json'}
                if t.csv.is_file(): files['results.csv']=t.csv
                seal_snapshot(attempt/'snapshots'/f'epoch_{t.epoch+1:04d}',files,
                              {'plan_sha256':plan['plan_sha256'],'arm':arm,'epoch':t.epoch+1,
                               'training_stop_requested':bool(t.stop),'resume_semantics':'native EMA/FP16 optimizer resume; RNG/dataloader state not restored; not bitwise exact'})
            trainer.add_callback('on_pretrain_routine_end',verify)
            trainer.add_callback('on_model_save',save)
            status['status']='training';write_json(attempt/'attempt_status.json',status)
            trainer.train()
            best=Path(trainer.best)
            shutil.copy2(best,attempt/'best.pt')
            status.update(status='evaluating',training_finished=True,training_seconds=time.monotonic()-started,
                          GPU_memory={'train_peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                                      'train_peak_reserved_bytes':torch.cuda.max_memory_reserved()},
                          best_sha256=file_digest(attempt/'best.pt'))
            write_json(attempt/'attempt_status.json',status)
            del trainer;gc.collect();torch.cuda.empty_cache()
            metrics=evaluate_arm(attempt/'best.pt',data,manifest,attempt,imgsz=plan['arms'][arm]['train_arguments']['imgsz'])
            load_block(block,data)
            status.update(status='complete',metrics=metrics)
            write_json(attempt/'validation_metrics.json',metrics)
        except BaseException as exc:
            status.update(status='interrupted_or_failed',error=f'{type(exc).__name__}: {exc}',
                          action='No per-arm batch fallback. OOM requires a new shared block; other interruptions may resume a sealed epoch snapshot in a new attempt.')
            raise
        finally:
            status['seconds']=time.monotonic()-started
            write_json(attempt/'attempt_status.json',status)
    return attempt,status


def resume_candidate(block, arm, plan):
    """Latest sealed epoch only; invalid latest evidence is an error, never silently bypassed."""
    attempts=Path(block)/arm/'attempts'
    statuses=[]
    for path in attempts.glob('attempt_*/attempt_status.json'):
        value=json.loads(path.read_text());statuses.append((path,value))
    for path,value in statuses:
        if 'OutOfMemoryError' in value.get('error',''):
            raise RuntimeError('This block had OOM; create a new ALL-arm common-batch block.')
    complete=[(path,value) for path,value in statuses if value.get('status')=='complete']
    if complete:
        path,value=max(complete,key=lambda pair:pair[0].parent.name)
        if value.get('plan_sha256')!=plan['plan_sha256'] or file_digest(path.parent/'best.pt')!=value['best_sha256']:
            raise ValueError('Completed attempt identity/hash changed.')
        return 'complete',path.parent
    evaluation_only=[(path,value) for path,value in statuses if value.get('training_finished') and value.get('best_sha256')]
    if evaluation_only:
        path,value=max(evaluation_only,key=lambda pair:pair[0].parent.name)
        if value.get('plan_sha256')!=plan['plan_sha256'] or file_digest(path.parent/'best.pt')!=value['best_sha256']:
            raise ValueError('Evaluation-only checkpoint identity changed.')
        return 'evaluate',path.parent/'best.pt'
    candidates=list(attempts.glob('attempt_*/snapshots/epoch_*/complete.json'))
    if not candidates: return 'fresh',None
    latest=max(candidates,key=lambda p:(int(p.parent.name.split('_')[-1]),p.parents[2].name))
    marker=validate_snapshot(latest.parent,plan,arm)
    if marker.get('epoch',0)>=plan['common']['epochs'] or marker.get('training_stop_requested'):
        return 'evaluate',latest.parent/'best.pt'
    return 'resume',latest.parent


def _run_block_authorized(block, dataset, preflight, *, training_authorized=False):
    """Future opt-in dispatcher. Completed arms are kept; interrupted ones use NEW attempts."""
    if not training_authorized: raise PermissionError('Training disabled; prepare/preflight only.')
    block,data,plan,_=load_block(block,dataset)
    # Any OOM blocks every remaining arm, including when failure was in another arm.
    candidates={arm:resume_candidate(block,arm,plan) for arm in plan['arms']}
    results={}
    for arm,spec in plan['arms'].items():
        if spec['status']=='skipped_identical_to_control':
            results[arm]={'status':'skipped_identical_to_control'};continue
        state,path=candidates[arm]
        if state=='complete': results[arm]={'status':'already_complete','attempt':str(path)};continue
        if state=='evaluate':
            attempt,status=evaluate_preserved_checkpoint(block,data,arm,preflight,path)
        else:
            attempt,status=run_arm(block,data,arm,preflight,training_authorized=True,resume_snapshot=path)
        results[arm]={'status':status['status'],'attempt':str(attempt)}
    return results



def evaluate_preserved_checkpoint(block, dataset, arm, preflight, best):
    """Recover an interruption after training completed, without resuming/repeating training."""
    block,data,plan,manifest=load_block(block,dataset)
    runtime=runtime_identity();verify_preflight(block,plan,preflight,runtime)
    best=Path(best).resolve()
    if not best.is_relative_to(block/arm/'attempts'): raise ValueError('Evaluation checkpoint outside this arm.')
    with arm_lock(block/arm):
        attempt=unique_directory(block/arm/'attempts','attempt')
        shutil.copy2(best,attempt/'best.pt')
        status={'status':'evaluating','arm':arm,'plan_sha256':plan['plan_sha256'],'runtime':runtime,
                'training_finished':True,'training_executed_this_attempt':False,'training_origin':str(best),
                'best_sha256':file_digest(attempt/'best.pt'),'metrics':None}
        write_json(attempt/'attempt_status.json',status)
        try:
            metrics=evaluate_arm(attempt/'best.pt',data,manifest,attempt,imgsz=plan['arms'][arm]['train_arguments']['imgsz'])
            write_json(attempt/'validation_metrics.json',metrics)
            load_block(block,data)
            status.update(status='complete',metrics=metrics)
        except BaseException as exc:
            status.update(status='interrupted_or_failed',error=f'{type(exc).__name__}: {exc}')
            raise
        finally: write_json(attempt/'attempt_status.json',status)
    return attempt,status



def run_block(block, dataset, preflight, *, training_authorized=False):
    """One block-wide dispatcher at a time; no automatic stale-lock takeover."""
    if not training_authorized: raise PermissionError('Training disabled; prepare/preflight only.')
    with arm_lock(Path(block)):
        return _run_block_authorized(block,dataset,preflight,training_authorized=True)
