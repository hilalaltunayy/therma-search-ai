"""Phase 07 synthetic controls only: no GPU, weights, training or model performance."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.data.audit import file_digest
from src.data.hit_uav_archive import HitUAVArchive
from src.training.hit_uav_yolo import prepare_hit_uav_yolo,validate_prepared_dataset,write_json
from src.training.phase07_plan import (read_baseline_evidence,resolve_plan,validate_plan,prepare_phase07,
                                      restore_data,TRAIN_FIELDS,data_identity,fingerprint)
from src.training.phase07_runtime import (memory_preflight,verify_preflight,run_arm,run_block,seal_snapshot,
                                        validate_snapshot,resume_candidate,arm_lock,verify_optimizer)
from test_yolo_training import make_training_fixture

ROOT=Path(__file__).resolve().parents[1]


def make_phase07_baseline(root):
    """Small explicit synthetic evidence, not a copy of private real experiment artifacts."""
    run=root/'baseline';run.mkdir(parents=True)
    archive=make_training_fixture(root/'source.zip')
    _,manifest=prepare_hit_uav_yolo(archive,root/'old_data',code_revision='synthetic',progress=None)
    write_json(run/'dataset_manifest.json',manifest)
    (run/'initial_weights').mkdir();(run/'initial_weights/yolo11s.pt').write_bytes(b'SYNTHETIC NOT A MODEL')
    args={k:0. for k in TRAIN_FIELDS}
    args.update(task='detect',mode='train',optimizer='auto',imgsz=640,epochs=40,patience=10,batch=8,nbs=64,
                seed=42,amp=False,half=False,cos_lr=False,lr0=.01,lrf=.01,momentum=.937,weight_decay=.0005,
                warmup_bias_lr=0.,warmup_epochs=3.,warmup_momentum=.8,scale=.5,mosaic=1.,close_mosaic=10,
                pretrained=True,deterministic=True,single_cls=False,rect=False,freeze=None,time=None,
                multi_scale=False,compile=False,cache=False,workers=0,val=True,split='val',iou=.7,max_det=300,
                fraction=1.,augment=False,agnostic_nms=False,copy_paste_mode='flip')
    write_json(run/'effective_train_arguments.json',args)
    (run/'ultralytics/train').mkdir(parents=True)
    # JSON is a strict YAML subset. No new PyYAML requirement for fixture generation.
    write_json(run/'ultralytics/train/args.yaml',{**args,'warmup_bias_lr':.1})
    groups=[{'initial_lr':.002,'lr':.002,'betas':[.9,.999],'eps':1e-8,'weight_decay':d,
             'amsgrad':False,'maximize':False} for d in (0.,.0005,0.)]
    write_json(run/'optimizer_effective.json',{'class':'AdamW','parameter_groups':groups})
    write_json(run/'run_summary.json',{'dataset_manifest_sha256':file_digest(run/'dataset_manifest.json'),
               'pretrained_sha256':file_digest(run/'initial_weights/yolo11s.pt'),
               'environment':{'ultralytics':'8.3.228','torch':'SYNTHETIC'}})
    return run,archive


def synthetic_runtime(): return {'gpu':{'name':'SYNTHETIC','device':0},'environment':{'packages':{'ultralytics':'8.3.228'}}}
def synthetic_probe(destination,data,plan,arm):
    return {'passed':True,'arm':arm,'imgsz':plan['arms'][arm]['train_arguments']['imgsz'],'optimizer_steps':0,'training_executed':False}


class Phase07Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.baseline,self.archive=make_phase07_baseline(self.root)

    def prepare(self,batch=4):
        return prepare_phase07(self.baseline,self.archive,self.root/'blocks',self.root/'work',git_commit='synthetic',batch=batch)

    def test_actual_optimizer_resolved_not_args_auto_defaults(self):
        evidence=read_baseline_evidence(self.baseline);plan=resolve_plan(evidence,git_commit='synthetic')
        self.assertEqual((plan['common']['optimizer'],plan['common']['lr0'],plan['common']['momentum']),('AdamW',.002,.9))
        self.assertEqual(plan['common']['warmup_bias_lr'],0.)
        self.assertEqual(plan['nominal_accumulation'],16)
        for arm,spec in plan['arms'].items():
            differences={k for k in plan['common'] if plan['common'][k]!=spec['train_arguments'][k]}
            self.assertEqual(differences,set(spec['overrides']))
        validate_plan(plan)

    def test_missing_evidence_or_effective_setting_blocks(self):
        path=self.baseline/'optimizer_effective.json';path.unlink()
        with self.assertRaises(FileNotFoundError): read_baseline_evidence(self.baseline)
        args=json.loads((self.baseline/'effective_train_arguments.json').read_text());del args['lrf']
        write_json(self.baseline/'effective_train_arguments.json',args)
        with self.assertRaises(FileNotFoundError): read_baseline_evidence(self.baseline)

    def test_missing_setting_and_unresolved_conflict_no_defaults(self):
        path=self.baseline/'effective_train_arguments.json';args=json.loads(path.read_text());del args['lrf'];write_json(path,args)
        with self.assertRaisesRegex(ValueError,'Missing actual baseline'): read_baseline_evidence(self.baseline)
        args['lrf']=.2;write_json(path,args)
        with self.assertRaisesRegex(ValueError,'Unresolved'): read_baseline_evidence(self.baseline)

    def test_optimizer_group_or_hash_corruption_blocks(self):
        path=self.baseline/'optimizer_effective.json';value=json.loads(path.read_text());value['parameter_groups'][1]['initial_lr']=.01;write_json(path,value)
        with self.assertRaisesRegex(ValueError,'Inconsistent'): read_baseline_evidence(self.baseline)
        (self.baseline/'initial_weights/yolo11s.pt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'identity mismatch'): read_baseline_evidence(self.baseline)

    def test_source_train_val_only_and_old_sources_unchanged(self):
        before={str(p):file_digest(p) for p in self.baseline.rglob('*') if p.is_file()}
        reader=HitUAVArchive.read
        def guarded(archive,member):
            self.assertNotIn('/test/',member);self.assertFalse(member.endswith('annotations/test.json'))
            return reader(archive,member)
        with patch.object(HitUAVArchive,'read',guarded): block,status=self.prepare()
        self.assertEqual(status['status'],'prepared_not_trained');self.assertFalse(status['training_executed'])
        data=Path(status['dataset_directory']);validate_prepared_dataset(data)
        self.assertIn('test: null',(data/'data.yaml').read_text())
        self.assertEqual(before,{str(p):file_digest(p) for p in self.baseline.rglob('*') if p.is_file()})
        manifest=json.loads((block/'dataset_manifest.json').read_text());self.assertEqual(set(manifest['splits']),{'train','val'})
        self.assertEqual(manifest['splits']['val']['excluded_images_by_reason'],{'zero_raw_annotations_pending_review':1,'contains_dontcare':1})

    def test_repeated_preparation_new_block_and_restore_after_loss(self):
        block,status=self.prepare();other,_=self.prepare();self.assertNotEqual(block,other)
        import shutil
        shutil.rmtree(status['dataset_directory'])
        data=restore_data(block,self.archive,self.root/'work')
        self.assertEqual(fingerprint(data_identity(json.loads((data/'dataset_manifest.json').read_text()))),json.loads((block/'frozen_plan.json').read_text())['train_val_identity_sha256'])

    def test_no_per_arm_batch_and_frozen_plan_drift(self):
        evidence=read_baseline_evidence(self.baseline)
        with self.assertRaises(ValueError): resolve_plan(evidence,batch=3,git_commit='synthetic')
        plan=resolve_plan(evidence,git_commit='synthetic');plan['arms']['P07-R1']['train_arguments']['batch']=2
        with self.assertRaises(ValueError): validate_plan(plan)
        plan['plan_sha256']=fingerprint({k:v for k,v in plan.items() if k!='plan_sha256'})
        with self.assertRaisesRegex(ValueError,'Per-arm'): validate_plan(plan)

    def test_identical_candidate_skipped(self):
        evidence=read_baseline_evidence(self.baseline);evidence['effective_args']['scale']=.25
        plan=resolve_plan(evidence,git_commit='synthetic');self.assertEqual(plan['arms']['P07-A1']['status'],'skipped_identical_to_control')

    def test_all_arm_memory_preflight_and_training_default_gate(self):
        block,status=self.prepare();data=Path(status['dataset_directory'])
        with patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime):
            out,record=memory_preflight(block,data,probe=synthetic_probe)
        self.assertEqual(record['status'],'passed');self.assertEqual({r['imgsz'] for r in record['results']},{640,960})
        plan=json.loads((block/'frozen_plan.json').read_text());verify_preflight(block,plan,out,synthetic_runtime())
        with self.assertRaises(PermissionError): run_arm(block,data,'P07-C0',out)
        with self.assertRaises(PermissionError): run_block(block,data,out)
        with self.assertRaises(ValueError): verify_preflight(block,plan,out,{'different_GPU':True})

    def test_memory_failure_blocks_entire_batch_and_gpu_absence_recorded(self):
        block,status=self.prepare();data=Path(status['dataset_directory'])
        def probe(*args): return {**synthetic_probe(*args),'passed':args[-1]!='P07-R1'}
        with patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime):
            out,record=memory_preflight(block,data,probe=probe)
        self.assertEqual(record['status'],'blocked_common_batch');self.assertIn('ALL arms',record['action'])
        with patch('src.training.phase07_runtime.runtime_identity',side_effect=RuntimeError('No GPU')):
            with self.assertRaises(RuntimeError): memory_preflight(block,data)
        self.assertTrue(any(json.loads(p.read_text())['status']=='blocked' for p in (block/'preflights').glob('*/memory_preflight.json')))

    def test_runtime_optimizer_drift_rejected(self):
        evidence=read_baseline_evidence(self.baseline);plan=resolve_plan(evidence,git_commit='synthetic')
        snapshot={**evidence['optimizer'],'accumulate':16,'scheduler':'LambdaLR'};verify_optimizer(snapshot,plan)
        snapshot['parameter_groups'][0]['betas']=[.937,.999]
        with self.assertRaises(ValueError): verify_optimizer(snapshot,plan)

    def test_snapshot_hash_arm_identity_and_no_overwrite(self):
        block,_=self.prepare();plan=json.loads((block/'frozen_plan.json').read_text())
        files={}
        for name in ('last.pt','best.pt','stopper.json'):
            path=self.root/name;path.write_bytes(b'SYNTHETIC');files[name]=path
        path=block/'P07-C0/attempts/attempt_1/snapshots/epoch_0001'
        seal_snapshot(path,files,{'arm':'P07-C0','plan_sha256':plan['plan_sha256']})
        self.assertEqual(resume_candidate(block,'P07-C0',plan),('resume',path))
        with self.assertRaises(FileExistsError): seal_snapshot(path,files,{})
        with self.assertRaises(ValueError): validate_snapshot(path,plan,'P07-A1')
        (path/'last.pt').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): resume_candidate(block,'P07-C0',plan)

    def test_mocked_interruption_resume_new_attempt_preserves_old_checkpoints(self):
        from types import SimpleNamespace
        import sys
        block,status=self.prepare();data=Path(status['dataset_directory'])
        with patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime):
            preflight,_=memory_preflight(block,data,probe=synthetic_probe)
        plan=json.loads((block/'frozen_plan.json').read_text());calls=[]
        class AdamW: pass
        class LambdaLR: pass
        def fake_trainer(destination,data,plan,arm,resume=None):
            calls.append((destination,resume));directory=destination/'weights';directory.mkdir(parents=True,exist_ok=True)
            class Trainer:
                def add_callback(self,key,callback): self.callbacks[key]=callback
                def train(self):
                    self.callbacks['on_pretrain_routine_end'](self)
                    self.last.write_bytes(b'SYNTHETIC LAST');self.best.write_bytes(b'SYNTHETIC BEST')
                    self.csv.write_text('epoch,loss\n1,1.0\n')
                    self.callbacks['on_model_save'](self)
                    if resume is None: raise RuntimeError('SYNTHETIC interruption after sealed epoch')
            t=Trainer();t.callbacks={};t.args=SimpleNamespace(**plan['arms'][arm]['train_arguments'])
            t.optimizer=AdamW();t.optimizer.param_groups=read_baseline_evidence(self.baseline)['optimizer']['parameter_groups']
            t.scheduler=LambdaLR();t.accumulate=16;t.stopper=SimpleNamespace(best_epoch=0,patience=10)
            t.stop=False;t.last=directory/'last.pt';t.best=directory/'best.pt';t.csv=destination/'results.csv';t.epoch=0 if resume is None else 1
            return t
        fake_torch=SimpleNamespace(cuda=SimpleNamespace(reset_peak_memory_stats=lambda:None,
                 max_memory_allocated=lambda:100,max_memory_reserved=lambda:200,empty_cache=lambda:None))
        with patch.dict(sys.modules,{'torch':fake_torch}),patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime),patch('src.training.phase07_runtime._trainer',fake_trainer),patch('src.training.phase07_runtime.evaluate_arm',return_value={'SYNTHETIC':True}):
            with self.assertRaisesRegex(RuntimeError,'SYNTHETIC interruption'):
                run_arm(block,data,'P07-C0',preflight,training_authorized=True)
            state,snapshot=resume_candidate(block,'P07-C0',plan);self.assertEqual(state,'resume')
            previous={str(p):file_digest(p) for p in snapshot.parent.parent.rglob('*') if p.is_file()}
            attempt,result=run_arm(block,data,'P07-C0',preflight,training_authorized=True,resume_snapshot=snapshot)
        self.assertEqual(result['status'],'complete');self.assertNotEqual(calls[0][0],calls[1][0])
        self.assertTrue(calls[1][1].is_relative_to(attempt/'resume_input'))
        self.assertEqual(previous,{p:file_digest(Path(p)) for p in previous})
        self.assertEqual(resume_candidate(block,'P07-C0',plan),('complete',attempt))

    def test_resume_adapter_routes_new_IO_and_rejects_argument_drift_before_write(self):
        import sys
        from types import SimpleNamespace
        from src.training.phase07_runtime import controlled_trainer_class
        plan=resolve_plan(read_baseline_evidence(self.baseline),git_commit='synthetic')
        settings=plan['common']
        class DetectionTrainer:
            def check_resume(self,overrides): pass
        fake={'ultralytics.models.yolo.detect':SimpleNamespace(DetectionTrainer=DetectionTrainer),
              'ultralytics.utils':SimpleNamespace(SETTINGS={})}
        destination=self.root/'new_attempt/train';yaml=self.root/'restored/data.yaml'
        with patch.dict(sys.modules,fake):
            cls=controlled_trainer_class(destination,settings,yaml)
            trainer=cls();trainer.args=SimpleNamespace(**settings,project='/old/run',name='train',save_dir='/old/run/train',data='/old/data.yaml')
            trainer.check_resume({})
            self.assertEqual(trainer.args.save_dir,str(destination));self.assertEqual(trainer.args.data,str(yaml))
            self.assertFalse(destination.exists())
            trainer.args.optimizer='auto'
            with self.assertRaisesRegex(ValueError,'optimizer'): trainer.check_resume({})
            self.assertFalse(destination.exists())

    def test_post_training_interruption_is_evaluation_only(self):
        block,_=self.prepare();plan=json.loads((block/'frozen_plan.json').read_text())
        directory=block/'P07-C0/attempts/attempt_1';directory.mkdir(parents=True)
        (directory/'best.pt').write_bytes(b'SYNTHETIC')
        write_json(directory/'attempt_status.json',{'status':'interrupted_or_failed','training_finished':True,
                   'plan_sha256':plan['plan_sha256'],'best_sha256':file_digest(directory/'best.pt')})
        self.assertEqual(resume_candidate(block,'P07-C0',plan),('evaluate',directory/'best.pt'))

    def test_block_lock_prevents_concurrent_dispatch_and_memory_probe(self):
        block,status=self.prepare();data=Path(status['dataset_directory'])
        with arm_lock(block):
            with self.assertRaises(FileExistsError): run_block(block,data,self.root/'unused',training_authorized=True)
            with patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime):
                with self.assertRaisesRegex(RuntimeError,'training lock'): memory_preflight(block,data,probe=synthetic_probe)

    def test_stale_lock_rejected_and_OOM_not_resumed(self):
        block,_=self.prepare();plan=json.loads((block/'frozen_plan.json').read_text())
        with arm_lock(block/'P07-C0'):
            with self.assertRaises(FileExistsError):
                with arm_lock(block/'P07-C0'): pass
        path=block/'P07-R1/attempts/attempt_1';path.mkdir(parents=True)
        write_json(path/'attempt_status.json',{'status':'interrupted_or_failed','error':'OutOfMemoryError: synthetic'})
        with self.assertRaisesRegex(RuntimeError,'ALL-arm'): resume_candidate(block,'P07-R1',plan)
