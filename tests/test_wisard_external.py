"""Phase 05 synthetic validation only: no real checkpoint, dataset or model performance."""
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
from src.data.wisard import WisardArchive
from src.data.wisard_sample import FOLDERS
from src.evaluation.wisard_external import run_wisard_external_evaluation, ExternalEvalConfig
from src.evaluation.wisard_external_data import prepare_ir_evaluation
from src.evaluation.wisard_external_metrics import small_object_recall, aggregate_fixed_records
from src.evaluation.person_detection import match_person_predictions


def make_external_fixture(path, labels=None, *, corrupt_ir=False, wrong_size=False):
    labels = labels if labels is not None else {
        1:'0 .5 .5 .0125 .015625\n',
        2:'0 .25 .25 .03125 .015625\n0 .75 .5 .0125 .0625\n',
        3:''}
    buffer=BytesIO()
    Image.new('L',(320,256) if wrong_size else (640,512),color=90).save(buffer,format='PNG')
    with ZipFile(path,'w') as z:
        for frame,text in labels.items():
            base=f'wrapper/{FOLDERS["IR"]}/frame_{frame:08d}'
            z.writestr(base+'.png',b'bad' if corrupt_ir else buffer.getvalue())
            if text is not None:
                z.writestr(base+'.txt',text)
        # Deliberately unreadable VIS. IR-only evaluation must never decode or read it.
        z.writestr(f'wrapper/{FOLDERS["VIS"]}/frame_00000000.png',b'NOT AN IMAGE')
    return path


class ArrayStub:
    def __init__(self,value): self.value=value
    def cpu(self): return self
    def tolist(self): return self.value


class ExternalModelStub:
    """Synthetic results for control-flow tests; has no train/save/download capability."""
    def __init__(self): self.calls=[]
    def val(self,**kwargs):
        self.calls.append(('val',kwargs))
        return SimpleNamespace(box=SimpleNamespace(map50=.4,map=.2),nt_per_class=[3],nt_per_image=[2],
            results_dict={'native_optimal_precision':.999},
            curves_results=[[[0,.5,1],[[1,.7,0]],'Recall','Precision']])
    def predict(self,**kwargs):
        self.calls.append(('predict',kwargs))
        frame=Path(kwargs['source']).stem
        boxes=[[316,252,324,260]] if frame.endswith('00000001') else [[150,124,170,132],[150,124,170,132]]
        scores=[.9] if len(boxes)==1 else [.8,.7]
        return [SimpleNamespace(orig_shape=(512,640),names={0:'Person'},boxes=SimpleNamespace(
            xyxy=ArrayStub(boxes),conf=ArrayStub(scores),cls=ArrayStub([0]*len(boxes))))]


def synthetic_environment():
    return {'python':'SYNTHETIC TEST','packages':{'ultralytics':'8.3.228','torch':'SYNTHETIC'}}


def synthetic_device():
    return {'device':'cpu','batch':1,'gpu_available':False,'torch_version':'SYNTHETIC'}


class ExternalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.archive=make_external_fixture(self.root/'synthetic.zip')
        self.model_path=self.root/'best.pt'
        self.model_path.write_bytes(b'SYNTHETIC ONLY, NOT A MODEL')

    def run_eval(self,model=None):
        model=model or ExternalModelStub()
        with patch('src.evaluation.wisard_external.environment_metadata',synthetic_environment), \
             patch('src.evaluation.wisard_external.evaluation_device',synthetic_device), \
             patch('src.evaluation.wisard_external.load_person_detector',return_value=model):
            return run_wisard_external_evaluation(self.model_path,self.archive,self.root/'reports',self.root/'work',git_commit='synthetic')

    def test_adapter_IR_only_with_empty_exclusion_and_exact_counts(self):
        original_read=WisardArchive.read
        def ir_only_read(source,member,**kwargs):
            self.assertNotIn(FOLDERS['VIS'],member)
            return original_read(source,member,**kwargs)
        before=file_digest(self.archive)
        with patch.object(WisardArchive,'read',ir_only_read):
            manifest=prepare_ir_evaluation(self.archive,self.root/'data',progress=None)
        self.assertEqual(file_digest(self.archive),before)
        self.assertEqual(manifest['status'],'ready')
        self.assertEqual((manifest['source_ir_image_candidates'],manifest['source_person_annotations_parsed'],manifest['empty_annotation_files']),(3,3,1))
        self.assertEqual((manifest['included_images'],manifest['excluded_images']),(2,1))
        empty=next(r for r in manifest['images'] if not r['included'])
        self.assertEqual(empty['reason'],'empty_annotation_pending_review')
        self.assertTrue((self.root/'data'/empty['image_path']).is_file())
        self.assertIn('train: null',(self.root/'data/evaluation.yaml').read_text())

    def test_malformed_labels_are_explicit_and_never_scored(self):
        for i,text in enumerate(['0 nan .5 .1 .1','1 .5 .5 .1 .1','0 .99 .5 .2 .2','0 .5 .5 .1 .1 .2','0 .5 .5 .1 0',None]):
            with self.subTest(text=text):
                archive=make_external_fixture(self.root/f'bad{i}.zip',{1:text})
                manifest=prepare_ir_evaluation(archive,self.root/f'data{i}',progress=None)
                self.assertEqual(manifest['status'],'invalid')
                self.assertTrue(manifest['issues'])
                self.assertEqual(manifest['included_images'],0)

    def test_bad_image_or_dimensions_block_preparation(self):
        for i,kwargs in enumerate([{'corrupt_ir':True},{'wrong_size':True}]):
            archive=make_external_fixture(self.root/f'bad_image{i}.zip',**kwargs)
            manifest=prepare_ir_evaluation(archive,self.root/f'image_data{i}',progress=None)
            self.assertEqual(manifest['status'],'invalid')
            self.assertTrue(any('IR_validation_error'==r['issue'] for r in manifest['issues']))

    def test_duplicate_annotations_block_native_dedup(self):
        archive=make_external_fixture(self.root/'duplicate.zip',{1:'0 .5 .5 .1 .1\n0 .5 .5 .1 .1'})
        manifest=prepare_ir_evaluation(archive,self.root/'duplicates',progress=None)
        self.assertEqual(manifest['status'],'invalid')
        self.assertIn('Tekrarlanan Person',str(manifest['issues']))

    def test_small_recall_strict_boundaries_and_global_match_indices(self):
        targets=[[0,0,8,8],[0,0,16,8],[0,0,8,32],[0,0,16,16]]
        result=small_object_recall(targets,[0,1])
        self.assertEqual(result['width_lt_16'],{'ground_truth_count':2,'detected_count':1,'missed_count':1,'recall':.5})
        self.assertEqual(result['height_lt_16']['recall'],1)
        self.assertEqual(result['both_lt_16']['ground_truth_count'],1)
        self.assertIsNone(small_object_recall([[0,0,20,20]],[])['both_lt_16']['recall'])
        with self.assertRaises(ValueError): small_object_recall(targets,[9])

    def test_matching_duplicate_prediction_FP_and_missed_GT_FN(self):
        detections=[{'bbox_xyxy':[0,0,8,8],'confidence':.9},{'bbox_xyxy':[0,0,8,8],'confidence':.8},
                    {'bbox_xyxy':[20,20,30,30],'confidence':.24}]
        result=match_person_predictions([[0,0,8,8],[20,20,30,30]],detections)
        self.assertEqual((result['tp'],result['fp'],result['fn']),(1,1,1))
        self.assertEqual(result['matches'][0]['target_index'],0)

    def test_zero_predictions_recall_zero_precision_null_and_iou_denominator(self):
        targets=[[0,0,8,8]]
        row={'ground_truth_xyxy':targets,'detections':[],'matching':match_person_predictions(targets,[])}
        metrics=aggregate_fixed_records([row])
        self.assertEqual(metrics['recall'],0)
        self.assertIsNone(metrics['precision'])
        self.assertEqual(metrics['small_object_recall']['both_lt_16']['recall'],0)
        self.assertEqual(metrics['localization_matched_iou']['n'],0)
        self.assertEqual(metrics['localization_best_iou_per_gt']['mean'],0)
        with self.assertRaises(ValueError): aggregate_fixed_records([])

    def test_fixed_protocol_rejects_threshold_search(self):
        with self.assertRaises(ValueError): ExternalEvalConfig(confidence=.3)
        with self.assertRaises(ValueError): ExternalEvalConfig(matching_iou=.75)

    def test_full_synthetic_outputs_and_native_map_separate_from_fixed(self):
        before=(file_digest(self.model_path),file_digest(self.archive))
        model=ExternalModelStub()
        out,summary=self.run_eval(model)
        self.assertEqual(summary['status'],'complete')
        self.assertEqual(before,(file_digest(self.model_path),file_digest(self.archive)))
        self.assertTrue(summary['inputs_unchanged'])
        self.assertEqual(summary['ultralytics_map']['mAP50'],.4)  # synthetic engine only
        fixed=summary['fixed_threshold']
        self.assertEqual((fixed['tp'],fixed['fp'],fixed['fn']),(2,1,1))
        self.assertAlmostEqual(fixed['precision'],2/3)
        self.assertAlmostEqual(fixed['recall'],2/3)
        self.assertEqual(fixed['false_positives_per_evaluated_image'],.5)
        self.assertEqual(fixed['small_object_recall']['width_lt_16']['recall'],.5)
        self.assertEqual(fixed['small_object_recall']['height_lt_16']['recall'],1)
        self.assertEqual(fixed['localization_matched_iou']['mean'],1)
        required=['evaluation_summary.json','evaluation_report.md','per_image_metrics.csv','exclusion_manifest.csv',
                  'predictions.jsonl','input_hashes.json','reproducibility.json','data_manifest.json','artifacts.json']
        self.assertTrue(all((out/name).is_file() for name in required))
        self.assertEqual(len((out/'predictions.jsonl').read_text().splitlines()),2)
        self.assertTrue((out/'figures/empty_annotation_review_01.png').is_file())
        self.assertTrue((out/'figures/small_person_01.png').is_file())
        self.assertTrue((out/'figures/map_curve_00_Precision_vs_Recall.png').is_file())
        with Image.open(out/'figures/confidence_and_localization.png') as image:
            self.assertAlmostEqual(image.info['dpi'][0],200,delta=.1)
        val=next(args for call,args in model.calls if call=='val')
        self.assertEqual((val['conf'],val['iou'],val['max_det'],val['imgsz']),(.001,.7,300,640))
        preds=[args for call,args in model.calls if call=='predict']
        self.assertEqual(len(preds),2)
        self.assertTrue(all(r['conf']==.25 for r in preds))
        self.assertIn('not interchangeable',(out/'evaluation_report.md').read_text())

    def test_missing_checkpoint_produces_failed_reports_without_model_load(self):
        self.model_path.unlink()
        with patch('src.evaluation.wisard_external.load_person_detector') as load:
            with self.assertRaises(FileNotFoundError):
                run_wisard_external_evaluation(self.model_path,self.archive,self.root/'reports',self.root/'work',git_commit='synthetic')
            load.assert_not_called()
        out=next((self.root/'reports').iterdir())
        summary=json.loads((out/'evaluation_summary.json').read_text())
        self.assertEqual(summary['status'],'failed')
        self.assertIsNone(summary['fixed_threshold'])
        self.assertTrue((out/'evaluation_report.md').exists())
        self.assertEqual((out/'predictions.jsonl').read_text(),'')

    def test_malformed_data_blocks_model_load_and_map(self):
        make_external_fixture(self.archive,{1:'0 nan .5 .1 .1'})
        with patch('src.evaluation.wisard_external.load_person_detector') as load:
            with self.assertRaisesRegex(ValueError,'Malformed'):
                run_wisard_external_evaluation(self.model_path,self.archive,self.root/'reports',self.root/'work',git_commit='synthetic')
            load.assert_not_called()
        out=next((self.root/'reports').iterdir())
        self.assertIsNone(json.loads((out/'evaluation_summary.json').read_text())['ultralytics_map'])

    def test_all_empty_images_have_review_evidence_and_no_fabricated_metrics(self):
        make_external_fixture(self.archive,{1:'',2:''})
        with self.assertRaises(ValueError): self.run_eval()
        out=next((self.root/'reports').iterdir())
        self.assertTrue((out/'figures/empty_annotation_review_01.png').exists())
        self.assertIsNone(json.loads((out/'evaluation_summary.json').read_text())['fixed_threshold'])

    def test_model_file_mutation_invalidates_scores(self):
        outer=self
        class MutatingModel(ExternalModelStub):
            def val(self,**kwargs):
                outer.model_path.write_bytes(b'SYNTHETIC MUTATION')
                return super().val(**kwargs)
        with self.assertRaisesRegex(RuntimeError,'Input hash changed'): self.run_eval(MutatingModel())
        out=next((self.root/'reports').iterdir())
        summary=json.loads((out/'evaluation_summary.json').read_text())
        self.assertFalse(summary['inputs_unchanged'])
        self.assertIsNone(summary['fixed_threshold'])

    def test_new_runs_preserve_prior_outputs(self):
        out,_=self.run_eval()
        note=out/'reviewer_notes.txt'
        note.write_text('keep')
        # Fast second run fails preflight, still creates its own directory and preserves first.
        self.model_path.unlink()
        with self.assertRaises(FileNotFoundError): self.run_eval()
        self.assertEqual(note.read_text(),'keep')
        self.assertEqual(len(list((self.root/'reports').iterdir())),2)


    def test_duplicate_frame_and_count_mismatch_are_diagnostic_errors(self):
        with ZipFile(self.archive,'a') as z:
            z.writestr(f'wrapper/{FOLDERS["IR"]}/alias_00000001.png',b'duplicate frame')
            z.writestr(f'wrapper/{FOLDERS["IR"]}/count.txt','number of humans: 999; number of images: 999')
        manifest=prepare_ir_evaluation(self.archive,self.root/'duplicate_frame',progress=None)
        self.assertEqual(manifest['status'],'invalid')
        self.assertIn('Tekrarlanan IR kare',str(manifest['issues']))
        self.assertIn('IR_count_txt_mismatch',str(manifest['issues']))

    def test_no_predictions_full_evaluation_is_zero_recall_not_fake_success(self):
        class NoDetectionsModel(ExternalModelStub):
            def val(self,**kwargs):
                self.calls.append(('val',kwargs))
                return SimpleNamespace(box=SimpleNamespace(map50=0,map=0),results_dict={},nt_per_class=[3],nt_per_image=[2])
            def predict(self,**kwargs):
                self.calls.append(('predict',kwargs))
                return [SimpleNamespace(orig_shape=(512,640),names={0:'Person'},boxes=None)]
        out,summary=self.run_eval(NoDetectionsModel())
        self.assertIsNone(summary['fixed_threshold']['precision'])
        self.assertEqual(summary['fixed_threshold']['recall'],0)
        self.assertEqual(summary['fixed_threshold']['fn'],3)
        self.assertFalse(summary['native_curves_available'])
        self.assertFalse(list((out/'figures').glob('true_positive_*.png')))
        self.assertTrue((out/'figures/false_negative_01.png').exists())

    def test_small_group_uses_normalized_size_measurement_without_xyxy_cancellation(self):
        # Supplied source width is exactly 16 px; reconstructed corner subtraction can drift.
        targets=[[100.00000000001,0,116,8]]
        result=small_object_recall(targets,[0],sizes=[[16,8]])
        self.assertEqual(result['width_lt_16']['ground_truth_count'],0)
        self.assertEqual(result['height_lt_16']['detected_count'],1)


    def test_native_gt_denominator_mismatch_blocks_all_scores(self):
        class SkippingModel(ExternalModelStub):
            def val(self,**kwargs):
                result=super().val(**kwargs)
                result.nt_per_class=[2]
                return result
        with self.assertRaisesRegex(ValueError,'denominators differ'):
            self.run_eval(SkippingModel())
        out=next((self.root/'reports').iterdir())
        self.assertIsNone(json.loads((out/'evaluation_summary.json').read_text())['ultralytics_map'])
