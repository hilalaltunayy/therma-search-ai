"""Gerçek WiSARD şemasını iddia etmeyen küçük sentetik arşiv testleri."""
import csv
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from src.data.wisard import (SOURCE, PairingSpec, LabelSpec, WisardArchive, sample_candidates,
                             inspect_wisard, match_pairs, parse_yolo_text, inspect_labels)
from src.data.wisard_reports import run_wisard_exploration, comparison_rows


def make_wisard_fixture(path):
    """Yalnızca test düzeni; gerçek klasör yapısına dair beyan değildir."""
    with ZipFile(path, 'w') as archive:
        for split, key in [('train', '001'), ('test', '002')]:
            for folder, mode, size in [('visible', 'RGB', (32, 24)), ('infrared', 'L', (20, 16))]:
                image = Image.new(mode, size, color=80 if mode == 'L' else (80, 110, 140))
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                archive.writestr(f'synthetic/flightA/{split}/{folder}/{key}.png', buffer.getvalue())
            archive.writestr(f'synthetic/flightA/{split}/labels/{key}.txt', '7 0.5 0.5 0.4 0.5\n')
        archive.writestr('synthetic/README.txt', 'Synthetic test data. Not a WiSARD license.')
        archive.writestr('synthetic/metadata.json', json.dumps({'example_only': True}))
    return path


def pairing_fixture():
    return PairingSpec(True,
        r'synthetic/(?P<flight>[^/]+)/(?P<split>[^/]+)/visible/(?P<key>\d+)\.png',
        r'synthetic/(?P<flight>[^/]+)/(?P<split>[^/]+)/infrared/(?P<key>\d+)\.png',
        'Synthetic test rule; not verified on real WiSARD')


def label_fixture():
    return LabelSpec(True, 'yolo_cxcywh_normalized',
                     r'synthetic/(?P<flight>[^/]+)/(?P<split>[^/]+)/infrared/(?P<stem>\d+)\.png',
                     'synthetic/{flight}/{split}/labels/{stem}.txt', {7:'Person'}, (7,),
                     'Synthetic 5-column fixture only')


class WisardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_source_claims_not_local_measurements_or_verified_license(self):
        self.assertEqual(SOURCE['official_claims_supplied_by_user']['synchronized_pairs'], 15453)
        self.assertTrue(SOURCE['official_claims_supplied_by_user']['pairs_are_subset_of_other_collections'])
        self.assertIsNone(SOURCE['version'])
        self.assertEqual(SOURCE['license']['status'], 'not_verified')

    def test_no_archive_source_only_report_is_complete(self):
        output, summary = run_wisard_exploration(self.root, code_revision='synthetic')
        self.assertEqual(summary['status'], 'source_only')
        self.assertIsNone(summary['local_image_count'])
        self.assertTrue((output / 'hit_uav_comparison.csv').exists())
        self.assertFalse((output / 'image_metadata.csv').exists())
        self.assertEqual(list(output.glob('*.png')), [])
        self.assertIn('Arşiv incelenmedi', comparison_rows()[1]['WiSARD'])

    def test_inventory_measures_actual_sizes_bands_without_modality_guess(self):
        path = make_wisard_fixture(self.root / 'WiSARD_sample.zip')
        with WisardArchive(path) as source:
            result = inspect_wisard(source)
        self.assertEqual(len(result['images']), 4)
        self.assertEqual({(r['width'],r['height'],r['channels']) for r in result['images']}, {(32,24,3),(20,16,1)})
        self.assertTrue(result['license_candidates'])
        self.assertIn('json_keys', next(r for r in result['label_previews'] if r['member'].endswith('.json')))
        self.assertTrue(all(not r['format_confirmed'] for r in result['label_previews']))
        self.assertFalse(result['errors'])

    def test_small_zip_discovery_and_full_archive_size_gate(self):
        path = make_wisard_fixture(self.root / 'WiSARD_sample.zip')
        candidates = sample_candidates(self.root)
        self.assertEqual(len(candidates),1)
        self.assertTrue(candidates[0]['eligible_sample_size'])
        with patch('src.data.wisard.MAX_SAMPLE_BYTES',1):
            with self.assertRaises(ValueError):
                WisardArchive(path)

    def test_unsafe_archive_is_rejected(self):
        path = self.root / 'bad.zip'
        with ZipFile(path,'w') as z:
            z.writestr('../escape.txt','bad')
        with self.assertRaises(ValueError):
            WisardArchive(path)

    def test_unconfirmed_pairing_and_labels_do_not_guess(self):
        self.assertEqual(match_pairs(['RGB/a.png','IR/a.png'],PairingSpec())['status'],'not_configured')
        self.assertEqual(inspect_labels(None,[],LabelSpec())['status'],'not_configured')
        with self.assertRaises(ValueError):
            match_pairs([],PairingSpec(True))

    def test_pairing_unique_keys_and_unverified_context(self):
        path = make_wisard_fixture(self.root / 'sample.zip')
        with WisardArchive(path) as source:
            result = inspect_wisard(source)
            pairs = match_pairs([r['member'] for r in result['images']],pairing_fixture())
        self.assertEqual(len(pairs['pairs']),2)
        self.assertFalse(pairs['issues'])
        self.assertTrue(all(r['status']=='unverified_path_tokens' for r in pairs['context_rows']))

    def test_ambiguous_missing_and_overlapping_pair_rules_reported(self):
        spec = PairingSpec(True,r'RGB/(?P<key>.+)\.png',r'IR/(?P<key>.+)\.png','synthetic')
        result = match_pairs(['RGB/a.png','IR/b.png'],spec)
        self.assertFalse(result['pairs'])
        self.assertEqual(len(result['issues']),2)
        # İki farklı uzantı aynı anahtara denk gelirse ilkini seçme.
        spec = PairingSpec(True,r'RGB/(?P<key>a)\..+',r'IR/(?P<key>a)\..+','synthetic')
        result = match_pairs(['RGB/a.png','RGB/a.jpg','IR/a.png'],spec)
        self.assertFalse(result['pairs'])
        spec = PairingSpec(True,r'(?P<key>.+)',r'(?P<key>.+)','synthetic')
        self.assertEqual(match_pairs(['a.png'],spec)['issues'][0]['issue'],'ambiguous_modality')

    def test_yolo_coordinates_only_with_explicit_confirmation(self):
        boxes, issues = parse_yolo_text('7 .5 .5 .4 .5',20,16,label_fixture())
        self.assertEqual(boxes[0][1].xyxy,(6,4,14,12))
        self.assertFalse(issues)
        with self.assertRaises(ValueError):
            parse_yolo_text('7 .5 .5 .4 .5',20,16,LabelSpec())
        unsupported = LabelSpec(True,'polygon',evidence='synthetic')
        with self.assertRaises(ValueError):
            parse_yolo_text('7 .5 .5 .4 .5',20,16,unsupported)

    def test_invalid_polygon_unknown_class_and_bounds_are_visible(self):
        boxes, issues = parse_yolo_text('7 0 0 .4 .5\n9 .5 .5 .2 .2\n7 .1 .1 .2 .2 .3 .3\n7 nan .5 .2 .2',20,16,label_fixture())
        self.assertEqual(len(boxes),1)  # Sınır dışı kutu korunur, kırpılmaz.
        self.assertEqual([r['issue'] for r in issues].count('invalid_label_row'),3)
        self.assertIn('box_out_of_bounds',[r['issue'] for r in issues])

    def test_confirmed_labels_use_real_image_resolution(self):
        path = make_wisard_fixture(self.root / 'sample.zip')
        with WisardArchive(path) as source:
            result = inspect_wisard(source)
            labels = inspect_labels(source,result['images'],label_fixture())
        self.assertEqual(labels['class_counts'],{'Person':2})
        self.assertEqual(labels['matched_images'],2)
        self.assertFalse(labels['issues'])

    def test_corrupt_image_is_reported_without_invented_dimensions(self):
        path = make_wisard_fixture(self.root / 'sample.zip')
        with ZipFile(path,'a') as z:
            z.writestr('unknown.png',b'bad image')
        with WisardArchive(path) as source:
            result = inspect_wisard(source)
        row = next(r for r in result['images'] if r['member']=='unknown.png')
        self.assertIsNone(row['width'])
        self.assertEqual(row['status'],'unreadable')
        self.assertEqual(len(result['errors']),1)

    def test_missing_annotation_is_not_automatic_negative(self):
        path = make_wisard_fixture(self.root / 'sample.zip')
        spec = label_fixture()
        spec = LabelSpec(True,spec.format,spec.image_regex,'absent/{stem}.txt',spec.class_names,(7,),spec.evidence)
        with WisardArchive(path) as source:
            result = inspect_wisard(source)
            labels = inspect_labels(source,result['images'],spec)
        self.assertEqual(len(labels['issues']),2)
        self.assertFalse(labels['empty_label_files'])

    def test_reports_preserve_source_and_previous_runs(self):
        import matplotlib
        matplotlib.use('Agg')
        from src.data.audit import file_digest
        path = make_wisard_fixture(self.root / 'sample.zip')
        before = file_digest(path)
        output, summary = run_wisard_exploration(self.root / 'reports',archive_path=path,
            pairing_spec=pairing_fixture(),label_spec=label_fixture(),code_revision='synthetic',max_previews=1,preview_members=['synthetic/metadata.json'])
        self.assertEqual(file_digest(path),before)
        extra=json.loads((output/'extra_metadata_previews.json').read_text())
        self.assertIn('example_only',extra[0]['json_keys'])
        self.assertEqual(summary['local_image_count'],4)
        self.assertEqual(len(list(output.glob('pair_*.png'))),1)
        self.assertEqual(len(list(output.glob('person_boxes_*.png'))),1)
        self.assertEqual(summary['flight_split_overlap_candidates'][0]['status'],'unverified_path_tokens')
        old = output / 'user_notes.txt'
        old.write_text('keep')
        new,_ = run_wisard_exploration(self.root / 'reports',code_revision='synthetic')
        self.assertNotEqual(output,new)
        self.assertEqual(old.read_text(),'keep')
        self.assertEqual(json.loads((output / 'wisard_summary.json').read_text())['status'],'complete')
