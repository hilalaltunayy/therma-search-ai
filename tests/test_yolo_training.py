"""Eğitim yapmadan sentetik dönüştürme, tanılama, inference ve orchestration testleri."""
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from src.data.audit import file_digest
from src.training.hit_uav_yolo import (prepare_hit_uav_yolo, validate_prepared_dataset,
                                      xyxy_to_yolo, read_yolo)
from src.training.baseline import BaselineConfig, require_gpu, choose_batch, run_baseline
from src.evaluation.person_detection import box_iou, match_person_predictions
from src.evaluation.inference import serialize_person_result, predict_person, load_person_detector


def make_training_fixture(path, mutate=None):
    """Her split: Person, zero-raw, Person+DontCare, diğer-sınıf-only."""
    buf = BytesIO()
    Image.new('L', (640, 512), 95).save(buf, format='PNG')
    with ZipFile(path, 'w') as z:
        for split in ('train', 'val', 'test'):
            data = {'images': [{'id': i, 'filename': f'{i}.png', 'width': 640, 'height': 512} for i in range(1, 5)],
                    'annotation': [
                        {'id': 1, 'image_id': 1, 'category_id': 0, 'bbox': [64, 128, 128, 256]},
                        {'id': 2, 'image_id': 3, 'category_id': 0, 'bbox': [5, 10, 20, 30]},
                        {'id': 3, 'image_id': 3, 'category_id': 4, 'bbox': [100, 100, 40, 40]},
                        {'id': 4, 'image_id': 4, 'category_id': 1, 'bbox': [10, 20, 40, 50]}]}
            if mutate:
                mutate(split, data)
            prefix = 'synthetic/normal_json/'
            z.writestr(prefix+f'annotations/{split}.json', json.dumps(data))
            for i in range(1, 5):
                z.writestr(prefix+f'{split}/{i}.png', buf.getvalue())
    return path


class TensorStub:
    def __init__(self, value):
        self.value = value
    def cpu(self):
        return self
    def tolist(self):
        return self.value


def result_stub(boxes=None):
    return SimpleNamespace(orig_shape=(512, 640), names={0:'Person'}, boxes=SimpleNamespace(
        xyxy=TensorStub(boxes or []), conf=TensorStub([.9]*len(boxes or [])), cls=TensorStub([0]*len(boxes or []))))


class FakeYOLO:
    """Gerçek eğitim/mAP yok. Sahte metrikler yalnızca test akışını sınar."""
    calls = []
    fail_train = False
    def __init__(self, path, task='detect'):
        self.path = Path(path)
        self.names = {0:'Person'}
        self.callbacks = {}
        if self.path.name == 'yolo11s.pt':
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(b'SYNTHETIC, NOT A MODEL')
        self.calls.append(('load', str(path)))
    def add_callback(self, name, callback):
        self.callbacks[name] = callback
    def train(self, **kwargs):
        self.calls.append(('train', kwargs))
        if self.fail_train:
            raise RuntimeError('synthetic training failure')
        folder = Path(kwargs['project'])/kwargs['name']
        (folder/'weights').mkdir(parents=True)
        (folder/'weights/best.pt').write_bytes(b'SYNTHETIC, NOT A MODEL')
        # Gerçek Ultralytics label indekslerini taklit et; sonraki test kapısı bunları tolere etmeli.
        for split in ('train', 'val'):
            (Path(kwargs['data']).parent/'labels'/f'{split}.cache').write_bytes(b'SYNTHETIC CACHE')
        fields = 'epoch,train/box_loss,train/cls_loss,train/dfl_loss,val/box_loss,val/cls_loss,val/dfl_loss\n'
        (folder/'results.csv').write_text(fields+'1,1,1,1,1,1,1\n')
        self.trainer = SimpleNamespace(save_dir=folder, args=SimpleNamespace(**kwargs), optimizer=SimpleNamespace(param_groups=[{'lr': .01, 'params': []}]))
        self.callbacks['on_train_start'](self.trainer)
    def val(self, **kwargs):
        self.calls.append(('val', kwargs))
        folder = Path(kwargs['project'])/kwargs['name']
        folder.mkdir(parents=True)
        Image.new('RGB',(20,20)).save(folder/'BoxPR_curve.png')
        return SimpleNamespace(box=SimpleNamespace(map50=.12, map=.08), results_dict={'SYNTHETIC/map': .08})
    def predict(self, **kwargs):
        self.calls.append(('predict', kwargs))
        return [result_stub([[64, 128, 192, 384]])]


def fake_runtime():
    """Patch set shared by notebook validator; production has no CPU training bypass."""
    return patch.multiple('src.training.baseline',
        require_gpu=lambda: {'name':'SYNTHETIC GPU', 'total_memory_bytes': 16*1024**3},
        version=lambda p: '8.3.228' if p == 'ultralytics' else 'synthetic')


def fake_modules():
    return {'ultralytics': SimpleNamespace(YOLO=FakeYOLO),
            'ultralytics.utils': SimpleNamespace(SETTINGS={})}


class TrainingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = make_training_fixture(self.root/'synthetic.zip')
        FakeYOLO.calls = []
        FakeYOLO.fail_train = False

    def prepare(self):
        return prepare_hit_uav_yolo(self.archive, self.root/'prepared', code_revision='synthetic', progress=None)

    def test_roundtrip_pixel_to_normalized(self):
        self.assertEqual(xyxy_to_yolo([64,128,192,384],640,512), (.2,.5,.2,.5))
        for actual, expected in zip(read_yolo('0 .2 .5 .2 .5',640,512)[0], [64,128,192,384]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(xyxy_to_yolo([0,0,640,512],640,512), (.5,.5,1,1))
        for box in ([-1,0,1,1], [0,0,641,1], [0,0,0,1], [0,0,float('nan'),1]):
            with self.assertRaises(ValueError):
                xyxy_to_yolo(box,640,512)

    def test_invalid_yolo_rows_rejected(self):
        for text in ('1 .5 .5 .1 .1','0 nan .5 .1 .1','0 .99 .5 .2 .2','0 .5 .5 0 .1','0 1 2 3 4 5'):
            with self.assertRaises(ValueError):
                read_yolo(text,640,512)

    def test_policies_preserve_source_and_split_with_explicit_exclusions(self):
        before = file_digest(self.archive)
        root, manifest = self.prepare()
        self.assertEqual(file_digest(self.archive), before)
        for split in ('train','val','test'):
            r = manifest['splits'][split]
            self.assertEqual(r['source_images'], 4)
            self.assertEqual(r['prepared'], {'images':2, 'labels':2, 'Person':1, 'person_background_images':1})
            self.assertEqual(r['excluded_images_by_reason'], {'zero_raw_annotations_pending_review':1, 'contains_dontcare':1})
            self.assertEqual(r['excluded_person_boxes_by_reason']['contains_dontcare'], 1)
            self.assertFalse((root/f'images/{split}/image_2.png').exists())
            self.assertFalse((root/f'images/{split}/image_3.png').exists())
            self.assertEqual((root/f'labels/{split}/image_4.txt').read_text(), '')
        self.assertEqual(manifest['status'], 'ready')
        self.assertEqual(len(manifest['cross_split_exact_byte_groups']), 1)
        validate_prepared_dataset(root)
        with self.assertRaises(FileExistsError):
            prepare_hit_uav_yolo(self.archive, root, code_revision='test')

    def test_corrupt_output_label_image_or_yaml_blocks_gate(self):
        root, _ = self.prepare()
        for relative in ('labels/train/image_1.txt','images/train/image_1.png','data.yaml'):
            path = root/relative
            original = path.read_bytes()
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError):
                validate_prepared_dataset(root)
            path.write_bytes(original)
        (root/'labels/train/extra.txt').write_text('')
        with self.assertRaises(ValueError):
            validate_prepared_dataset(root)

    def test_invalid_source_never_ready(self):
        for i, mutation in enumerate([
            lambda s,d: d['annotation'][0].update(bbox=[639,0,10,10]),
            lambda s,d: d['annotation'][0].update(category_id=99),
            lambda s,d: d['images'][1].update(id=1),
            lambda s,d: d['images'][0].update(width=10),
        ]):
            path = make_training_fixture(self.root/f'bad_{i}.zip', mutation)
            destination = self.root/f'bad_data_{i}'
            with self.assertRaises(ValueError):
                prepare_hit_uav_yolo(path, destination, code_revision='test', progress=None)
            self.assertEqual(json.loads((destination/'dataset_manifest.json').read_text())['status'], 'failed')

    def test_no_person_split_stops(self):
        path = make_training_fixture(self.root/'none.zip', lambda s,d: d['annotation'][0].update(category_id=1))
        with self.assertRaises(ValueError):
            prepare_hit_uav_yolo(path, self.root/'none_data', code_revision='test', progress=None)

    def test_gpu_guard_and_batch_decision(self):
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with self.assertRaisesRegex(RuntimeError, 'CPU eğitimi başlatılmadı'):
            require_gpu(fake)
        batch, reason = choose_batch(BaselineConfig(), {'total_memory_bytes': 4*1024**3})
        self.assertEqual(batch,4)
        self.assertEqual(reason['requested'],8)
        self.assertEqual(choose_batch(BaselineConfig(), {'total_memory_bytes':16*1024**3})[0],8)

    def test_match_duplicate_fp_and_unmatched_fn(self):
        predictions = [{'bbox_xyxy':[0,0,10,10],'confidence':.9},
                       {'bbox_xyxy':[0,0,10,10],'confidence':.8},
                       {'bbox_xyxy':[50,50,60,60],'confidence':.1}]
        r = match_person_predictions([[0,0,10,10],[20,20,30,30]],predictions)
        self.assertEqual((r['tp'],r['fp'],r['fn']), (1,1,1))
        self.assertEqual(r['fp_prediction_indices'], [1])
        self.assertEqual(r['fn_target_indices'],[1])
        self.assertEqual(box_iou([0,0,10,10],[10,10,20,20]),0)
        self.assertEqual(match_person_predictions([], predictions)['fp'],2)

    def test_inference_json_schema_no_training(self):
        result = serialize_person_result(result_stub([[64,128,192,384]]))
        self.assertEqual(result['image'], {'width':640,'height':512})
        self.assertEqual(result['detections'][0]['class_name'], 'Person')
        self.assertEqual(result['detections'][0]['confidence'],.9)
        json.dumps(result,allow_nan=False)
        invalid = result_stub()
        invalid.names = {0:'Car'}
        with self.assertRaises(ValueError):
            serialize_person_result(invalid)
        with self.assertRaises(ValueError):
            serialize_person_result(result_stub([[-1,0,10,10]]))
        with self.assertRaises(ValueError):
            load_person_detector(self.root/'absent.pt')

    def test_orchestration_train_val_selection_then_best_test_and_artifacts(self):
        with fake_runtime(), patch.dict('sys.modules', fake_modules()):
            out, summary = run_baseline(self.archive, self.root/'runs', self.root/'work', code_revision='synthetic')
        self.assertEqual(summary['status'],'complete_exploratory_baseline')
        self.assertFalse(summary['test_used_for_selection'])
        train = next(args for name,args in FakeYOLO.calls if name == 'train')
        self.assertEqual((train['epochs'],train['batch'],train['patience'],train['seed'],train['device']), (40,8,10,42,0))
        self.assertTrue(train['pretrained'])
        validations = [args for name,args in FakeYOLO.calls if name == 'val']
        self.assertEqual(len(validations),1)
        self.assertEqual(validations[0]['split'],'test')
        self.assertTrue(any(name == 'load' and args == str(out/'best.pt') for name,args in FakeYOLO.calls))
        self.assertTrue((out/'best.pt').is_file())
        for f in ('dataset_manifest.json','training_report.md','training_validation_losses.png',
                  'test_diagnostics/fixed_threshold_metrics.json','test_diagnostics/test_predictions.jsonl',
                  'ultralytics/test/BoxPR_curve.png','artifacts.json'):
            self.assertTrue((out/f).is_file(), f)
        metrics = summary['test_fixed_threshold']
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']),(1,1,0))
        self.assertEqual(metrics['precision'],.5)

    def test_training_failure_keeps_diagnostics_and_never_tests(self):
        FakeYOLO.fail_train = True
        with fake_runtime(), patch.dict('sys.modules', fake_modules()):
            with self.assertRaisesRegex(RuntimeError, 'synthetic training failure'):
                run_baseline(self.archive, self.root/'runs', self.root/'work', code_revision='synthetic')
        self.assertFalse(any(name == 'val' for name,_ in FakeYOLO.calls))
        out = next((self.root/'runs').iterdir())
        self.assertEqual(json.loads((out/'run_summary.json').read_text())['status'],'failed')
        self.assertTrue((out/'dataset_manifest.json').exists())

    def test_invalid_data_cannot_load_or_train_model(self):
        make_training_fixture(self.archive, lambda s,d:d['annotation'][0].update(bbox=[0,0,-10,20]))
        with fake_runtime(), patch.dict('sys.modules', fake_modules()):
            with self.assertRaises(ValueError):
                run_baseline(self.archive,self.root/'runs',self.root/'work',code_revision='synthetic')
        self.assertEqual(FakeYOLO.calls,[])


    def test_duplicate_person_rows_are_not_silently_deduplicated(self):
        def mutate(split, data):
            data['annotation'].append({**data['annotation'][0], 'id': 5})
        make_training_fixture(self.archive, mutate)
        with self.assertRaisesRegex(ValueError, 'Tekrarlanan Person'):
            self.prepare()

    def test_only_known_ultralytics_label_caches_are_allowed(self):
        root, _ = self.prepare()
        (root/'labels/train.cache').write_bytes(b'index')
        validate_prepared_dataset(root)
        (root/'labels/train/surprise.cache').write_bytes(b'not an expected index')
        with self.assertRaises(ValueError):
            validate_prepared_dataset(root)

    def test_zero_predictions_have_fn_and_undefined_precision(self):
        from src.training.baseline import fixed_threshold_test
        root, manifest = self.prepare()
        class EmptyModel:
            def predict(self, **kwargs):
                return [result_stub()]
        metrics = fixed_threshold_test(EmptyModel(), root, manifest, self.root/'diagnostics', BaselineConfig(), device='cpu')
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']), (0,0,1))
        self.assertIsNone(metrics['precision'])
        self.assertEqual(metrics['recall'],0)
        self.assertTrue((self.root/'diagnostics/false_negative_01.png').exists())

    def test_colab_bootstrap_without_gpu_never_clones_or_installs(self):
        import os
        notebook = json.loads((Path(__file__).resolve().parents[1]/'notebooks/04_hit_uav_yolo_training.ipynb').read_text())
        source = ''.join(notebook['cells'][2]['source'])
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with patch.dict(os.environ, {}, clear=True), patch.dict('sys.modules', {'torch':fake_torch}), patch('subprocess.run') as subprocess_run:
            with self.assertRaisesRegex(RuntimeError, 'CPU eğitimi başlatılmadı'):
                exec(source, {})
        subprocess_run.assert_not_called()
