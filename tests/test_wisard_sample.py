"""Küçük yapay görüntüler; gerçek WiSARD sayımı/senkronizasyon doğrulaması değildir."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from PIL import Image, ImageDraw

from src.data.audit import file_digest
from src.data.wisard import WisardArchive
from src.data.wisard_sample import (FOLDERS, discover_adapter, scan_sample, parse_sample_labels,
    modality_statistics, pairing_hypotheses, temporal_review, correlation)
from src.data.wisard_sample_reports import run_wisard_sample_analysis, evenly_spaced, turkish_summary


def make_sample(path, n=12, *, defects=False):
    """Aynı klasör/son-kare şeması, fakat yapay boyutlar ve içerik; B sayım uyumu daha iyi."""
    with ZipFile(path, 'w') as z:
        for mod, folder in FOLDERS.items():
            total = 0
            for i in range(n):
                frame = i+1 if mod == 'IR' else i
                prefix = f'wrapper/{folder}/frame_{frame:08d}'
                image = Image.new('L' if mod == 'IR' else 'RGB', (80, 64) if mod == 'IR' else (160, 90))
                ImageDraw.Draw(image).rectangle((10+i, 12, 20+i, 35), fill=200 if mod == 'IR' else (200, 150, 120))
                buf = BytesIO()
                image.save(buf, format='PNG')
                z.writestr(prefix+'.png', b'broken' if defects and mod == 'IR' and i == 4 else buf.getvalue())
                text = ('0 .5 .5 .1 .2\n'*(i % 4))
                total += i % 4
                if defects and mod == 'IR':
                    if i == 1:
                        continue
                    if i == 2:
                        text = '0 nan .5 .1 .2\n0 .99 .5 .2 .2\n9 .5 .5 .1 .2\n0 1 2 3 4 5\n'
                z.writestr(prefix+'.txt', text)
            z.writestr(f'wrapper/{folder}/count.txt', f'number of humans: {total}; number of images: {n}')
        z.writestr('wrapper/metadata.json', json.dumps({'note': 'synthetic only, not an official time mapping'}))
    return path


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def scan(self, path):
        with WisardArchive(path) as source:
            return scan_sample(source, discover_adapter(source.members))

    def test_known_adapter_and_unknown_fail_closed(self):
        path = make_sample(self.root/'s.zip')
        with WisardArchive(path) as source:
            self.assertTrue(discover_adapter(source.members)['enabled'])
            self.assertFalse(discover_adapter([*source.members, 'other/00000001.png'])['enabled'])
            self.assertFalse(discover_adapter(['RGB/00000001.png', 'IR/00000001.png'])['enabled'])
            self.assertFalse(discover_adapter([m.replace('frame_', 'frame_9') for m in source.members])['enabled'])

    def test_independent_counts_and_count_txt_exclusion(self):
        scan = self.scan(make_sample(self.root/'s.zip'))
        stats = modality_statistics(scan)
        self.assertEqual(len(scan['images']), 24)
        self.assertEqual(len(scan['count_files']), 2)
        self.assertEqual(stats['IR']['person_annotations'], 18)
        self.assertEqual(stats['VIS']['empty_labels'], 3)
        self.assertEqual(stats['VIS']['resolutions'], {'160x90': 12})
        self.assertEqual(stats['IR']['width_px']['median'], 8)
        self.assertEqual(stats['VIS']['width_px']['median'], 16)
        self.assertEqual(stats['IR']['small_objects']['both_sides_lt_16']['denominator'], 18)
        self.assertFalse(scan['issues'])

    def test_pairing_offset_scope_and_proxy_preference(self):
        scan = self.scan(make_sample(self.root/'s.zip'))
        pairs, evidence = pairing_hypotheses(scan)
        a, b = evidence['hypotheses'].values()
        self.assertEqual(a['candidate_pairs'], 11)
        self.assertEqual(b['candidate_pairs'], 12)
        self.assertEqual(evidence['IR_only_frame_numbers'], [12])
        self.assertEqual(evidence['VIS_only_frame_numbers'], [0])
        self.assertEqual(b['count_difference_absolute']['mean'], 0)
        self.assertEqual(b['count_difference_signed']['median'], 0)
        self.assertGreater(a['count_difference_absolute']['mean'], 0)
        self.assertEqual(evidence['preferred_provisional_hypothesis'], 'B_shift_minus_one')
        self.assertFalse(evidence['synchronization_confirmed'])
        self.assertEqual(len(pairs), 23)

    def test_exact_real_frame_ranges_without_real_image_claim(self):
        # 528 dosya yazmadan gerçek bildirilen ID kapsamını test eder.
        rows = [{'modality': mod, 'frame': i, 'member': f'{mod}/{i}', 'label_status': 'ok', 'person_count': 2}
                for mod, numbers in [('IR', range(1, 265)), ('VIS', range(264))] for i in numbers]
        _, ev = pairing_hypotheses({'images': rows})
        self.assertEqual(ev['hypotheses']['A_same_number']['candidate_pairs'], 263)
        self.assertEqual(ev['hypotheses']['B_shift_minus_one']['candidate_pairs'], 264)
        self.assertEqual(ev['hypotheses']['B_shift_minus_one']['coverage'], {'IR': 1.0, 'VIS': 1.0})
        self.assertFalse(ev['synchronization_confirmed'])

    def test_duplicates_never_pick_first(self):
        scan = self.scan(make_sample(self.root/'s.zip'))
        duplicate = dict(scan['images'][0], member='duplicate.png')
        scan['images'].append(duplicate)
        pairs, ev = pairing_hypotheses(scan)
        self.assertEqual(len(ev['duplicate_frame_keys']), 1)
        self.assertFalse(any(p['ir_member'] == duplicate['member'] or p['vis_member'] == duplicate['member'] for p in pairs))
        self.assertEqual(ev['hypotheses']['B_shift_minus_one']['candidate_pairs'], 11)

    def test_invalid_unknown_out_of_bounds_and_raw_ids(self):
        boxes, issues, observed = parse_sample_labels('0 nan .5 .1 .2\n0 .99 .5 .2 .2\n9 .5 .5 .1 .2\n0 1 2 3 4 5\n', 'synthetic', 80, 64)
        self.assertEqual(observed, {0: 3, 9: 1})
        self.assertEqual(len(boxes), 2)
        self.assertTrue(boxes[0]['out_of_bounds'])
        self.assertEqual(boxes[1]['label'], 'unknown_9')
        self.assertEqual(sum(r['issue'] == 'invalid_label_row' for r in issues), 2)
        self.assertEqual(boxes[1]['width_px'], 8)

    def test_corrupt_missing_and_bad_labels_do_not_become_negatives(self):
        scan = self.scan(make_sample(self.root/'bad.zip', defects=True))
        self.assertTrue({'missing_label','image_read_error','invalid_label_row','box_out_of_bounds','unknown_class_id'} <= {r['issue'] for r in scan['issues']})
        missing = next(r for r in scan['images'] if r['label_status'] == 'missing')
        self.assertIsNone(missing['person_count'])
        bad = next(r for r in scan['images'] if r['status'] == 'unreadable')
        self.assertIsNone(bad['width'])
        self.assertNotEqual(next(r for r in scan['images'] if r['invalid_rows'])['label_status'], 'empty')
        _, ev = pairing_hypotheses(scan)
        self.assertLess(ev['hypotheses']['B_shift_minus_one']['comparable_label_pairs'], 12)

    def test_temporal_hashes_within_modality_only(self):
        scan = self.scan(make_sample(self.root/'s.zip'))
        temporal = temporal_review(scan)
        self.assertEqual(temporal['compared_pairs'], {'IR': 66, 'VIS': 66})
        self.assertEqual(len(temporal['adjacent_frames']), 22)
        self.assertTrue(all(r['frame_gap'] == 1 for r in temporal['adjacent_frames']))
        self.assertTrue(all(FOLDERS[p['modality']] in p['left'] and FOLDERS[p['modality']] in p['right'] for p in temporal['near_or_exact_pairs']))
        self.assertIsNone(correlation([1,1,1], [1,2,3]))

    def test_spaced_visual_selection_is_distinct(self):
        selected = evenly_spaced(list(range(264)))
        self.assertEqual(len(set(selected)), 10)
        self.assertEqual((selected[0], selected[-1]), (0, 263))

    def test_report_outputs_ten_pairs_each_and_source_unchanged(self):
        path = make_sample(self.root/'s.zip')
        before = file_digest(path)
        out, summary = run_wisard_sample_analysis(self.root/'reports', archive_path=path, code_revision='synthetic', progress=None)
        self.assertEqual(file_digest(path), before)
        self.assertEqual(summary['status'], 'complete_provisional_pairing')
        self.assertEqual(summary['local_image_count'], 24)
        self.assertEqual(len(list(out.glob('pair_A_*.png'))), 10)
        self.assertEqual(len(list(out.glob('pair_B_*.png'))), 10)
        required = ['wisard_summary.json','image_metadata.csv','annotation_statistics.csv','pairing_hypotheses.csv',
                    'pairing_evidence.json','data_quality.json','hit_uav_comparison.csv','wisard_analysis_report.md']
        self.assertTrue(all((out/f).is_file() for f in required))
        quality = json.loads((out/'data_quality.json').read_text())
        self.assertTrue(all(r['matches'] for r in quality['count_txt_checks']))
        self.assertFalse(quality['empty_annotations_are_confirmed_negatives'])
        self.assertEqual(summary['problem_file_count'], 0)
        text = (out/'wisard_analysis_report.md').read_text()
        self.assertIn('Fiziksel senkronizasyon kesinleşmedi', text)
        self.assertIn('benzersiz kişi', text.lower())
        self.assertIn('Raporlar:', turkish_summary(out, summary))
        # Yalnızca önceki rapora sentinel; ikinci analiz kaynak verisiz, önceki dizine yazmaz.
        sentinel = out/'notes.txt'
        sentinel.write_text('keep')
        out2, _ = run_wisard_sample_analysis(self.root/'reports', archive_path=None, code_revision='test', progress=None)
        self.assertNotEqual(out, out2)
        self.assertEqual(sentinel.read_text(), 'keep')

    def test_missing_zip_produces_diagnostics_and_no_fake_zero_measurement(self):
        out, summary = run_wisard_sample_analysis(self.root/'reports', archive_path=self.root/'absent.zip', code_revision='test', progress=None)
        self.assertEqual(summary['status'], 'failed_with_diagnostics')
        self.assertIsNone(summary['local_image_count'])
        self.assertEqual(summary['modalities'], {})
        self.assertTrue((out/'wisard_analysis_report.md').exists())
        self.assertEqual(summary['problem_file_count'], 1)

    def test_unsafe_zip_produces_diagnostics(self):
        path = self.root/'unsafe.zip'
        with ZipFile(path, 'w') as z:
            z.writestr('../escape.txt', 'no')
        _, summary = run_wisard_sample_analysis(self.root/'reports', archive_path=path, code_revision='test', progress=None)
        self.assertEqual(summary['status'], 'failed_with_diagnostics')
        self.assertFalse((self.root/'escape.txt').exists())

    def test_unknown_structure_preserves_inventory_but_skips_semantics(self):
        path = self.root/'unknown.zip'
        with ZipFile(path, 'w') as z:
            buf = BytesIO()
            Image.new('L',(10,10)).save(buf, format='PNG')
            z.writestr('unknown/a.png',buf.getvalue())
            z.writestr('unknown/a.txt','0 .5 .5 .2 .2')
        out, summary = run_wisard_sample_analysis(self.root/'reports', archive_path=path, code_revision='test', progress=None)
        self.assertEqual(summary['status'], 'unknown_structure')
        self.assertEqual(summary['local_image_count'], 1)
        self.assertFalse(list(out.glob('*.png')))
        self.assertEqual(summary['pairing_candidate_counts'], {})

    def test_capture_time_hypotheses_and_coarse_time_limits(self):
        from src.data.wisard_sample import exif_pair_time_review
        scan = self.scan(make_sample(self.root/'s.zip'))
        for row in scan['images']:
            # Sentetik ortak saat: IR frame 1 ile VIS frame 0 aynı zaman.
            n = row['frame']-(1 if row['modality'] == 'IR' else 0)
            row['exif'] = {'36867': f'2026:01:01 12:00:{n:02d}'}
        pairs, _ = pairing_hypotheses(scan)
        evidence = exif_pair_time_review(scan, pairs)
        self.assertEqual(evidence['hypotheses']['B_shift_minus_one']['identical_capture_timestamp_pairs'], 12)
        self.assertEqual(evidence['hypotheses']['A_same_number']['absolute_time_difference_seconds']['mean'], 1)
        self.assertIn('kesin senkronizasyon değildir', evidence['interpretation'])
        self.assertEqual(evidence['images_with_subsecond_field'], 0)
        scan['images'][0]['exif'] = {'36867': 'bad timestamp'}
        self.assertEqual(len(exif_pair_time_review(scan, pairs)['parse_errors']), 1)

    def test_missing_count_and_orphan_labels_are_quality_findings(self):
        # Count TXT olmaması, orphan etiket ve hatalı count.txt ayrı sorunlar.
        path = make_sample(self.root/'s.zip', n=3)
        replacement = self.root/'changed.zip'
        with ZipFile(path) as src, ZipFile(replacement, 'w') as dst:
            for member in src.namelist():
                if member.endswith('count.txt'):
                    if FOLDERS['IR'] in member:
                        continue
                    dst.writestr(member, 'number of humans: 999; number of images: 999')
                else:
                    dst.writestr(member, src.read(member))
            dst.writestr(f'wrapper/{FOLDERS["IR"]}/frame_99999999.txt', '0 .5 .5 .2 .2')
        out, summary = run_wisard_sample_analysis(self.root/'reports', archive_path=replacement, code_revision='test', progress=None)
        quality = json.loads((out/'data_quality.json').read_text())
        self.assertEqual(quality['issue_counts']['missing_count_txt'], 1)
        self.assertEqual(quality['issue_counts']['count_txt_mismatch'], 1)
        self.assertEqual(quality['issue_counts']['orphan_label'], 1)
        self.assertEqual(summary['status'], 'complete_with_issues')
        self.assertEqual(summary['problem_file_count'], 3)
