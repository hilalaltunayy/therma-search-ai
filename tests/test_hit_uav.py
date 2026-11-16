"""Kullanıcı tarafından doğrulanan alan adlarıyla küçük sentetik HIT-UAV fixture'ları."""
import csv
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from PIL import Image

from src.data.hit_uav import parse_hit_uav
from src.data.hit_uav_archive import HitUAVArchive, audit_hit_uav_zip, size_summary
from src.data.hit_uav_reports import save_audit_reports


def hit_fixture():
    return {
        'images': [{'id': 1, 'filename': 'a.png', 'width': 640, 'height': 512},
                   {'id': 2, 'filename': 'negative.png', 'width': 640, 'height': 512}],
        'categories': [{'id': i, 'name': n} for i, n in enumerate(
            ('Person', 'Car', 'Bicycle', 'OtherVehicle', 'DontCare'))],
        'annotation': [
            {'id': 1, 'image_id': 1, 'category_id': 0, 'bbox': [10, 20, 12, 19]},
            {'id': 2, 'image_id': 1, 'category_id': 4, 'bbox': [40, 50, 30, 30]},
            {'id': 3, 'image_id': 1, 'category_id': 1, 'bbox': [100, 100, 40, 20]},
        ],
    }


def make_archive(path, *, root='HIT-UAV-v1.2.1/', mutate=None):
    """Fixture ZIP'i üretir; gerçek veri veya gerçek sayımlar içermez."""
    buffer = BytesIO()
    image = Image.new('L', (640, 512), color=90)
    image.save(buffer, format='PNG')
    content = buffer.getvalue()
    with ZipFile(path, 'w') as archive:
        for split in ('train', 'val', 'test'):
            data = hit_fixture()
            if mutate:
                mutate(split, data)
            prefix = root + 'normal_json/'
            archive.writestr(prefix + f'annotations/{split}.json', json.dumps(data))
            archive.writestr(prefix + split + '/a.png', content)
            archive.writestr(prefix + split + '/negative.png', content)
    return path


class HitUAVTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_real_field_names_mapping_and_xywh(self):
        result = parse_hit_uav(hit_fixture())
        self.assertEqual(result.samples[0].boxes[0].xyxy, (10, 20, 22, 39))
        self.assertEqual(result.samples[0].boxes[1].label, 'DontCare')
        self.assertEqual(result.samples[1].boxes, ())
        self.assertEqual(result.raw_counts['Person'], 1)
        self.assertEqual(result.person_sizes, [(12, 19)])
        self.assertFalse(result.issues)

    def test_generic_coco_is_not_silently_accepted(self):
        data = hit_fixture()
        data['annotations'] = data.pop('annotation')
        with self.assertRaises(ValueError):
            parse_hit_uav(data)

    def test_invalid_bounds_and_references_reported_separately(self):
        data = hit_fixture()
        for index, fields in enumerate([
            {'bbox': [0, 0, -1, 2]}, {'bbox': [0, 0, float('nan'), 2]},
            {'bbox': [635, 10, 12, 19]}, {'image_id': 99}, {'category_id': 99},
        ], start=4):
            data['annotation'].append({**data['annotation'][0], 'id': index, **fields})
        result = parse_hit_uav(data)
        kinds = {i['issue'] for i in result.issues}
        self.assertEqual(kinds, {'invalid_bbox', 'box_out_of_bounds', 'missing_image_reference', 'unknown_category_id'})
        self.assertEqual(result.raw_annotation_records, 8)
        self.assertEqual(result.person_sizes, [(12, 19)])
        self.assertEqual(result.raw_counts['Unknown'], 1)
        self.assertEqual(len(result.samples[0].boxes), 4)  # OOB saklanır; istatistiğe girmez.

    def test_coordinate_overflow_is_invalid(self):
        data = hit_fixture()
        data['annotation'][0]['bbox'] = [1e308, 0, 1e308, 10]
        result = parse_hit_uav(data)
        self.assertIn('invalid_bbox', [i['issue'] for i in result.issues])
        self.assertFalse(result.person_sizes)

    def test_duplicates_and_unsafe_filenames_quarantined(self):
        for change in ('image_id', 'filename', 'annotation_id', 'unsafe'):
            data = hit_fixture()
            if change == 'image_id':
                data['images'][1]['id'] = 1
            elif change == 'filename':
                data['images'][1]['filename'] = 'a.png'
            elif change == 'annotation_id':
                data['annotation'][1]['id'] = 1
            else:
                data['images'][0]['filename'] = '../a.png'
            self.assertTrue(parse_hit_uav(data).issues, change)

    def test_class_mapping_mismatch_is_visible(self):
        data = hit_fixture()
        data['categories'][0]['name'] = 'Wrong'
        self.assertIn('category_mapping_mismatch', [i['issue'] for i in parse_hit_uav(data).issues])

    def test_default_resolution_use_is_recorded(self):
        data = hit_fixture()
        del data['images'][0]['width']
        result = parse_hit_uav(data)
        self.assertEqual(result.dimensions_from_default, 1)
        self.assertEqual(result.samples[0].width, 640)

    def test_person_size_denominator_and_empty_case(self):
        result = size_summary([(12, 19), (20, 30)])
        self.assertEqual(result['median_width_px'], 16)
        self.assertEqual(result['at_least_one_side_lt16_fraction'], .5)
        self.assertIsNone(size_summary([])['median_width_px'])
        self.assertIsNone(size_summary([])['at_least_one_side_lt16_fraction'])

    def test_zip_root_discovery_and_counts_without_extraction(self):
        archive = make_archive(self.root / 'fixture.zip')
        expected = {s: {'images': 2, 'objects': 3, 'Person': 1} for s in ('train', 'val', 'test')}
        report, _ = audit_hit_uav_zip(archive, expected_counts=expected)
        self.assertEqual(report['normal_json_root'], 'HIT-UAV-v1.2.1/normal_json/')
        for result in report['splits'].values():
            self.assertEqual(result['readable_images'], 2)
            self.assertEqual(result['resolutions'], {'640x512': 2})
            self.assertTrue(all(v['matches'] for v in result['previous_count_comparison'].values()))
            self.assertEqual(result['objects_by_class_raw']['DontCare'], 1)
        self.assertEqual(report['cross_split_filename_overlap']['train__test']['image_basenames'], ['a.png', 'negative.png'])
        self.assertEqual(list(self.root.iterdir()), [archive])

    def test_absent_version_prefix_also_supported(self):
        archive = make_archive(self.root / 'fixture.zip', root='')
        with HitUAVArchive(archive) as source:
            self.assertEqual(source.root, 'normal_json/')

    def test_unsafe_and_ambiguous_zip_rejected(self):
        archive = make_archive(self.root / 'fixture.zip')
        with ZipFile(archive, 'a') as z:
            z.writestr('../escape.txt', 'bad')
        with self.assertRaises(ValueError):
            HitUAVArchive(archive)
        archive = make_archive(self.root / 'ambiguous.zip')
        with ZipFile(archive, 'a') as z:
            z.writestr('copy/normal_json/annotations/train.json', '{}')
        with self.assertRaises(ValueError):
            HitUAVArchive(archive)

    def test_member_size_limit_applies_before_read(self):
        archive = make_archive(self.root / 'fixture.zip')
        with HitUAVArchive(archive, max_member_bytes=1) as source:
            with self.assertRaises(ValueError):
                source.read(source.root + 'annotations/train.json')

    def test_missing_corrupt_and_mismatched_images(self):
        def mutate(split, data):
            data['images'][1]['filename'] = 'missing.png'
            data['images'][0]['width'] = 600
        archive = make_archive(self.root / 'fixture.zip', mutate=mutate)
        with ZipFile(archive, 'a') as z:
            z.writestr('HIT-UAV-v1.2.1/normal_json/train/broken.png', b'bad')
        report, _ = audit_hit_uav_zip(archive)
        item = report['splits']['train']
        self.assertEqual(item['missing_images'], ['missing.png'])
        self.assertEqual(item['unannotated_images'], ['broken.png', 'negative.png'])
        self.assertEqual(item['issue_counts']['dimension_mismatch'], 1)
        self.assertEqual(item['issue_counts']['unreadable_image'], 1)

    def test_skip_image_validation_and_reference_mismatch_are_explicit(self):
        archive = make_archive(self.root / 'fixture.zip')
        report, _ = audit_hit_uav_zip(archive, verify_images=False)
        item = report['splits']['train']
        self.assertEqual(item['image_validation'], 'not_run')
        self.assertIsNone(item['readable_images'])
        self.assertFalse(item['previous_count_comparison']['images']['matches'])

    def test_persistent_outputs_csv_json_and_sample_limit(self):
        import matplotlib
        matplotlib.use('Agg')
        archive = make_archive(self.root / 'fixture.zip')
        report, loaded = audit_hit_uav_zip(archive)
        output = save_audit_reports(report, loaded, archive, self.root / 'reports', code_revision='synthetic-test')
        metadata = json.loads((output / 'analysis_metadata.json').read_text())
        self.assertEqual(metadata['status'], 'complete')
        self.assertFalse(metadata['archive']['md5_recomputed_in_this_run'])
        self.assertEqual(len(metadata['selected_samples']), 3)
        self.assertEqual(len(list(output.glob('*.png'))), 5)
        self.assertEqual(len(metadata['outputs']), 7)
        with (output / 'split_statistics.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['DontCare'], '1')
        self.assertEqual(rows[0]['Person'], '1')
        self.assertEqual(json.loads((output / 'data_quality.json').read_text())['splits']['train']['image_files'], 2)
        with self.assertRaises(ValueError):
            save_audit_reports(report, loaded, archive, self.root, code_revision='test', samples_per_split=4)


if __name__ == '__main__':
    unittest.main()
