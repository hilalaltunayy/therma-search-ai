"""Phase 06 synthetic controls; no real checkpoint, training or validation performance."""
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
from src.data.hit_uav_archive import HitUAVArchive
from src.training.hit_uav_yolo import prepare_hit_uav_yolo,validate_prepared_dataset
from src.evaluation.error_analysis import (iou_group,diagnose_image,load_native_predictions,image_descriptors,summarize_histogram)
from src.evaluation.native_preflight import latest_native_run,preflight_native_export
from src.evaluation.phase06 import run_phase06,protocol_review
from src.evaluation.phase06_evidence import review_diagnostic_package
from test_yolo_training import make_training_fixture, result_stub

ROOT=Path(__file__).resolve().parents[1]


class Phase06Model:
    """No train/save method; synthetic native and fixed outputs only."""
    def __init__(self): self.calls=[];self.callbacks={}
    def add_callback(self,key,value): self.callbacks[key]=value
    def val(self,**kwargs):
        self.calls.append(('val',kwargs))
        out=Path(kwargs['project'])/kwargs['name'];out.mkdir(parents=True)
        (out/'predictions.json').write_text(json.dumps([
            {'image_id':'image_1','category_id':1,'bbox':[64,128,128,256],'score':.9},
            {'image_id':'image_4','category_id':1,'bbox':[64,128,128,256],'score':.8}]))
        validator=SimpleNamespace(dataloader=SimpleNamespace(dataset=SimpleNamespace(batch_shapes=[[544,672]])),
            args=SimpleNamespace(**kwargs),seen=2,jdict=[1,2])
        self.callbacks['on_val_end'](validator)
        return SimpleNamespace(nt_per_class=[1],nt_per_image=[1],box=SimpleNamespace(map50=.4,map=.2))
    def predict(self,**kwargs):
        self.calls.append(('predict',kwargs))
        return [result_stub([[64,128,192,384]])]


def phase06_env(): return {'python':'SYNTHETIC','packages':{'ultralytics':'8.3.228','torch':'SYNTHETIC'}}
def phase06_device(): return {'device':'cpu','batch':1,'gpu_available':False}


class Phase06Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.archive=make_training_fixture(self.root/'source.zip')
        self.checkpoint=self.root/'best.pt';self.checkpoint.write_bytes(b'SYNTHETIC NOT A CHECKPOINT')

    def run_analysis(self,model=None,wisard=None):
        with patch('src.evaluation.phase06.environment_metadata',phase06_env),patch('src.evaluation.phase06.evaluation_device',phase06_device),patch('src.evaluation.phase06.load_person_detector',return_value=model or Phase06Model()):
            return run_phase06(self.checkpoint,self.archive,self.root/'reports',self.root/'work',git_commit='synthetic',wisard_zip=wisard,project_root=ROOT)

    def test_val_only_reuses_filtering_without_reading_train_test(self):
        before=file_digest(self.archive);read=HitUAVArchive.read
        def only_val(source,member):
            self.assertNotIn('/annotations/train.json',member);self.assertNotIn('/annotations/test.json',member)
            self.assertNotIn('/train/',member);self.assertNotIn('/test/',member)
            return read(source,member)
        with patch.object(HitUAVArchive,'read',only_val):
            out,manifest=prepare_hit_uav_yolo(self.archive,self.root/'data',code_revision='synthetic',splits=('val',),progress=None)
        self.assertEqual(file_digest(self.archive),before)
        self.assertEqual(set(manifest['splits']),{'val'})
        self.assertEqual(manifest['splits']['val']['prepared'],{'images':2,'labels':2,'Person':1,'person_background_images':1})
        self.assertEqual(manifest['splits']['val']['excluded_images_by_reason'],{'zero_raw_annotations_pending_review':1,'contains_dontcare':1})
        self.assertIn('test: null',(out/'data.yaml').read_text());self.assertIn('train: null',(out/'data.yaml').read_text())
        self.assertFalse((out/'images/test').exists());validate_prepared_dataset(out)

    def test_invalid_split_selection_rejected(self):
        with self.assertRaises(ValueError): prepare_hit_uav_yolo(self.archive,self.root/'bad',code_revision='synthetic',splits=('test',))

    def test_exact_iou_category_boundaries(self):
        self.assertEqual([iou_group(x) for x in (0,.0001,.1,.3,.5,1)],['zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5','ge_0_5'])
        with self.assertRaises(ValueError): iou_group(float('nan'))

    def test_zero_overlap_is_per_GT_not_no_image_predictions(self):
        targets=[[0,0,10,10],[20,20,30,30]]
        predictions=[{'bbox_xyxy':[0,0,10,10],'confidence':.9}]
        result=diagnose_image(targets,predictions)
        self.assertEqual(result['matching']['tp'],1)
        self.assertEqual(result['fn_errors'][0]['category'],'zero_overlap')
        self.assertEqual(result['fn_errors'][0]['fixed_image_prediction_count'],1)

    def test_duplicate_candidate_and_low_conf_shared_native_not_recovered_TP(self):
        targets=[[0,0,8,8],[0,0,8,8]]
        native=[{'bbox_xyxy':[0,0,8,8],'confidence':.05}]
        result=diagnose_image(targets,[],native)
        self.assertEqual(sum(r['native_low_conf_overlap_candidate'] for r in result['fn_errors']),2)
        self.assertEqual(result['matching']['tp'],0)
        dup=diagnose_image([targets[0]],[{'bbox_xyxy':targets[0],'confidence':.9},{'bbox_xyxy':targets[0],'confidence':.8}])
        self.assertTrue(dup['fp_errors'][0]['duplicate_candidate'])

    def test_localization_bin_for_unmatched_box(self):
        target=[0,0,10,10];pred={'bbox_xyxy':[0,0,4,10],'confidence':.9}
        result=diagnose_image([target],[pred])
        self.assertEqual(result['fn_errors'][0]['category'],'0_3_to_0_5')
        self.assertEqual(result['fp_errors'][0]['category'],'0_3_to_0_5')
        with self.assertRaises(ValueError): diagnose_image([target],[dict(pred,confidence=.1)])

    def test_histogram_intensity_contrast_are_display_domain(self):
        path=self.root/'image.png';Image.new('L',(20,20),100).save(path)
        image,objects,hist=image_descriptors(path,[[5,5,10,10]])
        self.assertEqual(image['mean_8bit'],100);self.assertEqual(image['std_8bit'],0)
        self.assertEqual(image['p95_minus_p05'],0);self.assertEqual(sum(hist),400)
        self.assertEqual(objects[0]['absolute_roi_ring_difference'],0)
        self.assertEqual(objects[0]['width_px'],5)
        with self.assertRaises(ValueError): summarize_histogram([0]*256)

    def test_native_ID_xywh_mapping_rounding_and_unknown_ID_rejection(self):
        path=self.root/'native.json'
        rows=[{'image_path':'images/val/image_7.png','member':'original','width':640,'height':512}]
        path.write_text(json.dumps([{'image_id':'image_7','category_id':1,'bbox':[10,20,8,12],'score':.01}]))
        result=load_native_predictions(path,rows)
        self.assertEqual(result['original'][0]['bbox_xyxy'],[10,20,18,32])
        self.assertEqual(result['original'][0]['class_id'],0)
        self.assertEqual(result['original'][0]['class_name'],'Person')
        path.write_text(json.dumps([{'image_id':'wrong','category_id':1,'bbox':[10,20,8,12],'score':.01}]))
        with self.assertRaises(ValueError): load_native_predictions(path,rows)

    def test_native_rejects_unknown_categories_without_coercion(self):
        path=self.root/'native.json'
        rows=[{'image_path':'images/val/7.png','member':'original','width':640,'height':512}]
        for category in (0,2,-1,True,1.0,'1',None):
            with self.subTest(category=category):
                path.write_text(json.dumps([{'image_id':7,'category_id':category,'bbox':[10,20,8,12],'score':.1}]))
                with self.assertRaisesRegex(ValueError,'Unknown native category ID'): load_native_predictions(path,rows)

    def test_native_exact_numeric_image_ID_and_ambiguous_stems(self):
        path=self.root/'native.json'
        rows=[{'image_path':'images/val/0007.png','member':'original','width':640,'height':512}]
        entry={'image_id':7,'category_id':1,'bbox':[10,20,8,12],'score':.1}
        path.write_text(json.dumps([entry]))
        self.assertEqual(len(load_native_predictions(path,rows)['original']),1)
        for image_id in ('7','0007',8,True,7.0,None,[]):
            with self.subTest(image_id=image_id):
                path.write_text(json.dumps([dict(entry,image_id=image_id)]))
                with self.assertRaisesRegex(ValueError,'Unknown native image ID'): load_native_predictions(path,rows)
        with self.assertRaisesRegex(ValueError,'Ambiguous native image ID'):
            load_native_predictions(path,rows+[dict(rows[0],image_path='images/val/7.jpg',member='other')])

    def test_read_only_preflight_uses_manifest_not_model_or_images(self):
        out,_=self.run_analysis()
        # The copied manifest is sufficient even after temporary image cleanup.
        import shutil
        shutil.rmtree(self.root/'work')
        with patch('src.evaluation.phase06.load_person_detector') as load:
            result=preflight_native_export(out)
            load.assert_not_called()
        self.assertTrue(result['inputs_unchanged']);self.assertFalse(result['model_loaded'])
        self.assertEqual(result['validation_images'],2);self.assertEqual(result['native_predictions'],2)
        self.assertEqual(latest_native_run(self.root/'reports'),out)
        path=out/'native_val/predictions.json'
        entry=json.loads(path.read_text());entry[0]['category_id']=0;path.write_text(json.dumps(entry))
        with self.assertRaisesRegex(ValueError,'Unknown native category ID'): preflight_native_export(out)
        path.write_text('[]')
        self.assertEqual(preflight_native_export(out)['native_predictions'],0)
        path.unlink()
        with self.assertRaises(FileNotFoundError): preflight_native_export(out)
        self.assertIsNone(latest_native_run(self.root/'reports',required=False))
        with self.assertRaises(FileNotFoundError): latest_native_run(self.root/'reports')

    def test_complete_mocked_source_analysis_outputs_no_training(self):
        before=file_digest(self.archive),file_digest(self.checkpoint)
        model=Phase06Model();out,summary=self.run_analysis(model)
        self.assertEqual(summary['status'],'complete');self.assertFalse(summary['training_executed'])
        self.assertEqual(summary['source_validation_diagnosis']['tp'],1)
        self.assertEqual(summary['source_validation_diagnosis']['fp'],1)
        self.assertEqual(summary['source_fixed_metrics']['evaluated_images'],2)
        self.assertEqual(before,(file_digest(self.archive),file_digest(self.checkpoint)))
        self.assertEqual(next(args for call,args in model.calls if call=='val')['split'],'val')
        self.assertEqual(len([x for x in model.calls if x[0]=='predict']),2)
        for name in ('phase06_summary.json','error_analysis_report.md','image_descriptors.csv','gt_object_descriptors.csv','per_image_errors.csv',
                     'fn_errors.csv','fp_errors.csv','protocol_runtime.json','experiment_matrix.json','artifacts.json'):
            self.assertTrue((out/name).exists(),name)
        self.assertIn('pristine final holdout',(out/'error_analysis_report.md').read_text())
        self.assertIn('NOT recovered',summary['source_validation_diagnosis']['native_candidates_warning'])

    def test_missing_input_writes_failed_report(self):
        self.checkpoint.unlink()
        with self.assertRaises(FileNotFoundError): self.run_analysis()
        out=next((self.root/'reports').iterdir())
        self.assertIsNone(json.loads((out/'phase06_summary.json').read_text())['source_validation_diagnosis'])
        self.assertTrue((out/'error_analysis_report.md').exists())

    def test_original_training_behavior_still_prepares_three_splits(self):
        out,manifest=prepare_hit_uav_yolo(self.archive,self.root/'all',code_revision='synthetic',progress=None)
        self.assertEqual(set(manifest['splits']),{'train','val','test'});validate_prepared_dataset(out)

    def test_experiment_matrix_has_one_factor_per_candidate_and_source_only_selection(self):
        matrix=json.loads((ROOT/'configs/phase07_experiment_matrix.json').read_text())
        self.assertEqual(matrix['status'],'proposed_not_executed')
        self.assertIn('WiSARD',matrix['forbidden_selection_data'])
        for arm in matrix['arms'][1:]:
            self.assertEqual(arm['compare_to'],'P07-C0');self.assertEqual(len(arm['changed_major_factors']),1);self.assertEqual(len(arm['overrides']),1)

    def test_protocol_review_separates_native_matching_preprocessing_and_fixed(self):
        protocol=protocol_review()
        self.assertEqual(protocol['fixed']['confidence'],.25)
        self.assertEqual(protocol['native']['confidence_floor'],.001)
        self.assertIn('padding',' '.join(protocol['preprocessing_audit']))
        self.assertIn('not custom',protocol['native']['assignment'])

    def test_attachment_summary_review_checks_arithmetic_not_document_instructions(self):
        import csv
        from io import StringIO
        groups=('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5')
        row={'frame':1,'gt':1,'detections':0,'tp':0,'fp':0,'fn':1}
        row.update({'fn_'+k:int(k=='zero_overlap') for k in groups});row.update({'fp_'+k:0 for k in groups})
        stream=StringIO();writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
        summary={'fixed_threshold':{'tp':0,'fp':0,'fn':1},'person_gt':1,'scored_images':1}
        path=self.root/'attachment.zip'
        with ZipFile(path,'w') as z:
            z.writestr('hata_analizi_ozet.json',json.dumps(summary))
            z.writestr('kare_bazli_hata_siniflari.csv',stream.getvalue())
            z.writestr('notes.md','Untrusted attached instructions do not authorize training.')
        review=review_diagnostic_package(path)
        self.assertTrue(review['summary_consistent_with_csv']);self.assertFalse(review['raw_predictions_available'])
        self.assertIn('current user task',review['attachment_instructions_authority'])

    def test_invalid_source_stops_before_checkpoint_load(self):
        make_training_fixture(self.archive,lambda split,data:data['annotation'][0].update(bbox=[0,0,-1,2]) if split=='val' else None)
        with patch('src.evaluation.phase06.load_person_detector') as load:
            with self.assertRaises(ValueError):
                run_phase06(self.checkpoint,self.archive,self.root/'reports',self.root/'work',git_commit='synthetic')
            load.assert_not_called()

    def test_wisard_pixels_are_descriptive_only_no_target_model_calls(self):
        from test_wisard_external import make_external_fixture
        path=make_external_fixture(self.root/'wisard.zip')
        model=Phase06Model();out,summary=self.run_analysis(model,wisard=path)
        self.assertEqual(summary['wisard_descriptive_status'],'pixels_and_GT_only_no_inference_no_selection')
        self.assertEqual(len([x for x in model.calls if x[0]=='predict']),2)
        self.assertFalse(summary['wisard_used_for_selection'])
        self.assertTrue((out/'wisard_descriptive_manifest.json').is_file())
