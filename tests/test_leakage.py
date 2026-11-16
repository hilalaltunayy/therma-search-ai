"""Sızıntı araçları için sentetik testler; gerçek HIT-UAV bulgusu üretmez."""
import csv
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from PIL import Image

from src.data.leakage import ReviewConfig, compare_splits, dhash, naming_hypothesis, pixel_sha256, scan_archive
from src.data.leakage_reports import run_leakage_review


def make_review_zip(path):
    """Bir sıfır anotasyonlu, bir DontCare'lı ve bir bozuk anotasyonlu görüntü/split."""
    from test_hit_uav import hit_fixture
    buffer = BytesIO()
    Image.new('L', (640, 512), color=90).save(buffer, format='PNG')
    image = buffer.getvalue()
    with ZipFile(path, 'w') as archive:
        for split in ('train', 'val', 'test'):
            data = hit_fixture()
            # a.png yalnızca DontCare içerir; negative.png gerçekten sıfır anotasyonludur.
            data['annotation'] = [data['annotation'][1]]
            data['images'].append({'id': 3, 'filename': 'broken_label.png', 'width': 640, 'height': 512})
            data['annotation'].append({'id': 99, 'image_id': 3, 'category_id': 0, 'bbox': [0, 0, -1, 2]})
            prefix = 'version/normal_json/'
            archive.writestr(prefix + f'annotations/{split}.json', json.dumps(data))
            for name in ('a.png', 'negative.png', 'broken_label.png'):
                archive.writestr(prefix + split + '/' + name, image)
    return path


def record(split, name, byte_hash, pixel_hash, value):
    return {'split': split, 'filename': name, 'member': split+'/'+name,
            'byte_sha256': byte_hash, 'pixel_sha256': pixel_hash,
            'dhash_hex': f'{value:016x}', 'decode_status': 'ok'}


class LeakageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_dhash_known_direction_and_uniform_case(self):
        image = Image.new('L', (9, 8))
        image.putdata([x*20 for y in range(8) for x in range(9)])
        self.assertEqual(dhash(image), 0)
        image.putdata([(8-x)*20 for y in range(8) for x in range(9)])
        self.assertEqual(dhash(image), 2**64-1)
        self.assertEqual(dhash(Image.new('L', (640, 512), 90)), 0)

    def test_pixel_hash_ignores_encoding_but_preserves_mode_size_and_palette(self):
        from PIL.PngImagePlugin import PngInfo
        image = Image.new('L', (20, 10), 80)
        a, b = BytesIO(), BytesIO()
        info = PngInfo()
        info.add_text('fixture', 'different metadata')
        image.save(a, format='PNG')
        image.save(b, format='PNG', pnginfo=info)
        self.assertNotEqual(a.getvalue(), b.getvalue())
        a.seek(0); b.seek(0)
        with Image.open(a) as left, Image.open(b) as right:
            self.assertEqual(pixel_sha256(left), pixel_sha256(right))
        self.assertNotEqual(pixel_sha256(image), pixel_sha256(image.convert('RGB')))
        self.assertNotEqual(pixel_sha256(image), pixel_sha256(Image.new('L', (10, 20), 80)))
        palette_a, palette_b = Image.new('P', (2, 2)), Image.new('P', (2, 2))
        palette_a.putpalette([0]*768)
        palette_b.putpalette([255]*768)
        self.assertNotEqual(pixel_sha256(palette_a), pixel_sha256(palette_b))
        transparent = image.copy()
        transparent.info['transparency'] = 80
        self.assertNotEqual(pixel_sha256(image), pixel_sha256(transparent))

    def test_exact_bytes_pixels_and_candidates_separate(self):
        records = [record('train', 'a', 'byteA', 'pixelA', 3),
                   record('val', 'b', 'byteA', 'pixelA', 3),
                   record('test', 'c', 'byteB', 'pixelA', 3),
                   record('test', 'd', 'byteC', 'pixelC', 7)]
        exact, near, groups, summary = compare_splits(records, ReviewConfig(dhash_threshold=1))
        self.assertEqual(summary['compared_cross_split_pairs'], 5)
        self.assertEqual(summary['exact_pairs'], 3)
        self.assertEqual(summary['near_candidate_pairs'], 2)
        self.assertEqual({p['classification'] for p in exact},
                         {'confirmed_identical_file_bytes', 'confirmed_identical_decoded_pixels'})
        self.assertTrue(all(p['classification'] == 'review_candidate' for p in near))
        self.assertEqual(len(groups), 2)

    def test_threshold_boundary_and_same_split_exclusion(self):
        records = [record('train', 'a', 'a', 'a', 3), record('train', 'b', 'b', 'b', 7),
                   record('test', 'c', 'c', 'c', 15)]
        _, near, _, summary = compare_splits(records, ReviewConfig(dhash_threshold=1))
        self.assertEqual(summary['compared_cross_split_pairs'], 2)
        self.assertEqual(len(near), 1)
        self.assertEqual(near[0]['left_filename'], 'b')
        _, near, _, _ = compare_splits(records, ReviewConfig(dhash_threshold=0))
        self.assertEqual(near, [])

    def test_pair_limits_are_explicit_and_full_exact_members_retained(self):
        records = [record(split, str(i), 'same', 'same', 3)
                   for split in ('train', 'val', 'test') for i in range(3)]
        exact, _, groups, summary = compare_splits(records, ReviewConfig(max_exact_pairs=2))
        self.assertEqual(summary['exact_pairs'], 27)
        self.assertTrue(summary['exact_csv_truncated'])
        self.assertEqual(len(exact), 2)
        self.assertTrue(all(len(g['members']) == 9 for g in groups))
        for i, row in enumerate(records):
            row['byte_sha256'] = row['pixel_sha256'] = str(i)
        _, near, _, summary = compare_splits(records, ReviewConfig(max_near_pairs=2, dhash_threshold=0))
        self.assertEqual(summary['near_candidate_pairs'], 27)
        self.assertTrue(summary['near_csv_truncated'])
        self.assertEqual(len(near), 2)

    def test_low_information_candidates_are_flagged_and_ranked_last(self):
        rows = [record('train', 'blank', 'a', 'a', 0), record('val', 'blank2', 'b', 'b', 0),
                record('train', 'pattern', 'c', 'c', 3), record('val', 'pattern2', 'd', 'd', 3)]
        _, near, _, _ = compare_splits(rows, ReviewConfig(dhash_threshold=0, max_near_pairs=1))
        self.assertFalse(near[0]['low_information_hash'])
        _, near, _, _ = compare_splits(rows[:2], ReviewConfig(dhash_threshold=0))
        self.assertTrue(near[0]['low_information_hash'])

    def test_unreadable_images_excluded_from_pair_comparison(self):
        rows = [record('train', 'a', 'a', 'a', 3), record('val', 'bad', 'a', 'a', 3)]
        rows[1]['decode_status'] = 'unreadable'
        _, _, _, summary = compare_splits(rows, ReviewConfig())
        self.assertEqual(summary['compared_cross_split_pairs'], 0)
        self.assertEqual(summary['excluded_unreadable_images'], 1)

    def test_config_rejects_invalid_threshold_limits_and_regex(self):
        for kwargs in ({'dhash_threshold': -1}, {'dhash_threshold': 65}, {'dhash_threshold': True},
                       {'max_near_pairs': 0}, {'max_pair_previews': 31}, {'contact_page_size': 0},
                       {'group_pattern': r'(.+)'}):
            with self.assertRaises(ValueError):
                ReviewConfig(**kwargs)

    def test_name_groups_are_unverified_hypotheses(self):
        result = naming_hypothesis('scene_001.jpg', ReviewConfig().group_pattern)
        self.assertEqual(result['group_candidate'], 'scene')
        self.assertEqual(result['frame_token'], '001')
        self.assertEqual(result['group_status'], 'unverified_filename_hypothesis')
        self.assertEqual(naming_hypothesis('123.jpg', ReviewConfig().group_pattern)['group_status'], 'not_inferred')

    def test_zero_raw_annotations_distinct_from_dontcare_and_invalid_boxes(self):
        archive = make_review_zip(self.root / 'fixture.zip')
        _, review, errors, _ = scan_archive(archive, ReviewConfig())
        self.assertEqual(len(review), 6)
        self.assertEqual(sum(r['selection_reason'] == 'zero_raw_annotations' for r in review), 3)
        self.assertFalse(any(r['filename'] == 'a.png' for r in review))
        invalid = [r for r in review if r['filename'] == 'broken_label.png']
        self.assertTrue(all(r['selection_reason'] == 'annotations_present_but_no_accepted_boxes' for r in invalid))
        self.assertTrue(errors)

    def test_missing_records_and_corrupt_files_remain_visible(self):
        archive = make_review_zip(self.root / 'fixture.zip')
        with ZipFile(archive, 'a') as stream:
            stream.writestr('version/normal_json/train/orphan.png', b'not image data')
        _, review, errors, _ = scan_archive(archive, ReviewConfig())
        orphan = next(r for r in review if r['filename'] == 'orphan.png')
        self.assertEqual(orphan['selection_reason'], 'missing_or_invalid_image_record')
        self.assertEqual(orphan['decode_status'], 'unreadable')
        self.assertTrue(orphan['byte_sha256'])
        self.assertIn('image_read_error', [r['issue'] for r in errors])

    def test_persistent_contact_csv_pairs_and_no_source_mutation(self):
        import matplotlib
        matplotlib.use('Agg')
        from src.data.audit import file_digest
        archive = make_review_zip(self.root / 'fixture.zip')
        before = file_digest(archive)
        config = ReviewConfig(max_pair_previews=2, contact_page_size=1)
        output, summary = run_leakage_review(archive, self.root / 'reports', code_revision='synthetic', config=config)
        self.assertEqual(file_digest(archive), before)
        self.assertEqual(summary['zero_raw_annotation_counts'], {'train': 1, 'val': 1, 'test': 1})
        self.assertEqual(len(list(output.glob('contact_sheet_*.png'))), 6)
        self.assertEqual(len(list(output.glob('suspicious_pair_*.png'))), 2)
        with (output / 'manual_review.csv').open(encoding='utf-8-sig') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r['human_present'] == '' for r in rows))
        self.assertTrue(all(r['reviewer'] == '' for r in rows))
        self.assertEqual(summary['comparison']['exact_pairs'], 27)
        self.assertTrue((output / 'near_duplicate_candidates.csv').is_file())
        self.assertEqual(json.loads((output / 'leakage_summary.json').read_text())['status'], 'complete_with_errors')
        self.assertFalse(any(p.suffix == '.zip' for p in output.iterdir()))

    def test_rerun_preserves_previous_manual_decisions(self):
        archive = make_review_zip(self.root / 'fixture.zip')
        config = ReviewConfig(max_pair_previews=0, contact_page_size=40)
        a, _ = run_leakage_review(archive, self.root / 'reports', code_revision='synthetic', config=config)
        manual = a / 'manual_review.csv'
        manual.write_text('user decision preserved')
        b, _ = run_leakage_review(archive, self.root / 'reports', code_revision='synthetic', config=config)
        self.assertNotEqual(a, b)
        self.assertEqual(manual.read_text(), 'user decision preserved')
