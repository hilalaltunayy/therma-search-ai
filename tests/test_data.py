"""Küçük sentetik dosyalarla testler; gerçek HIT-UAV istatistiği üretmez."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from src.data.annotations import Box, Sample, load_coco, load_voc, safe_relative, to_xyxy
from src.data.audit import audit_split, duplicate_report, file_digest, plot_sample
from src.data.download import download_zenodo_file, extract_zip, inspect_zip, zenodo_metadata
from src.data.exploration import run_exploration
from src.data.inventory import inventory, preview_label


def coco_fixture():
    return {'images': [{'id': 1, 'file_name': 'a.png', 'width': 20, 'height': 10},
                       {'id': 2, 'file_name': 'negative.png', 'width': 20, 'height': 10}],
            'categories': [{'id': 4, 'name': 'Person'}, {'id': 9, 'name': 'DontCare'}],
            'annotations': [{'id': 7, 'image_id': 1, 'category_id': 4, 'bbox': [2, 3, 4, 5]},
                            {'id': 8, 'image_id': 1, 'category_id': 9, 'bbox': [1, 1, 2, 2]}]}


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.label = self.root / 'labels.json'
        self.label.write_text(json.dumps(coco_fixture()))

    def test_box_formats(self):
        self.assertEqual(to_xyxy([5, 6, 4, 2], 'cxcywh'), (3, 5, 7, 7))
        self.assertEqual(to_xyxy([3, 5, 4, 2], 'xywh'), (3, 5, 7, 7))
        for values in ([0, 0, 0, 1], [0, 0, -1, 2], [0, 0, float('nan'), 1], [1, 2, 3, 4, 5]):
            with self.assertRaises(ValueError):
                to_xyxy(values, 'xywh')
        with self.assertRaises(ValueError):
            to_xyxy([1, 2, 3, 4], 'guess')

    def test_coco_preserves_classes_and_negatives(self):
        samples = load_coco(self.label, bbox_format='xywh')
        self.assertEqual(samples[0].boxes[0], Box('Person', (2, 3, 6, 8)))
        self.assertEqual(samples[0].boxes[1].label, 'DontCare')
        self.assertEqual(samples[1].boxes, ())
        self.assertIn('images', preview_label(self.label))

    def test_coco_rejects_bad_references_and_duplicates(self):
        for mutation in ('image_id', 'category_id', 'duplicate_image', 'duplicate_ann', 'duplicate_path'):
            data = coco_fixture()
            if mutation in {'image_id', 'category_id'}:
                data['annotations'][0][mutation] = 999
            elif mutation == 'duplicate_image':
                data['images'].append(data['images'][0])
            elif mutation == 'duplicate_path':
                data['images'][1]['file_name'] = 'a.png'
            else:
                data['annotations'].append(data['annotations'][0])
            self.label.write_text(json.dumps(data))
            with self.assertRaises(ValueError, msg=mutation):
                load_coco(self.label, bbox_format='xywh')

    def test_voc_origin(self):
        path = self.root / 'label.xml'
        path.write_text('<annotation><filename>a.png</filename><size><width>20</width><height>10</height></size>'
                        '<object><name>Person</name><bndbox><xmin>1</xmin><ymin>1</ymin>'
                        '<xmax>20</xmax><ymax>10</ymax></bndbox></object></annotation>')
        self.assertEqual(load_voc(path, coordinate_origin='one_inclusive').boxes[0].xyxy, (0, 0, 20, 10))
        self.assertEqual(load_voc(path, coordinate_origin='zero_half_open').boxes[0].xyxy, (1, 1, 20, 10))
        with self.assertRaises(ValueError):
            load_voc(path, coordinate_origin='guess')

    def test_inventory_and_quality(self):
        Image.new('L', (20, 10)).save(self.root / 'a.png')
        Image.new('L', (20, 10)).save(self.root / 'extra.png')
        (self.root / 'broken.jpg').write_bytes(b'not an image')
        samples = load_coco(self.label, bbox_format='xywh')
        samples.append(Sample('extra.png', 99, 10, (Box('Car', (-1, 0, 22, 5)),)))
        report = audit_split(self.root, samples, hash_images=True)
        self.assertEqual(report['image_files'], 3)
        self.assertEqual(report['readable_images'], 2)
        self.assertEqual(report['resolutions'], {'20x10': 2})
        self.assertEqual(report['missing_images'], ['negative.png'])
        self.assertEqual(report['objects_by_class']['Person'], 1)
        self.assertEqual(report['images_by_class']['DontCare'], 1)
        self.assertEqual({x['issue'] for x in report['issues']},
                         {'unreadable_image', 'dimension_mismatch', 'box_out_of_bounds'})
        self.assertEqual(len(inventory(self.root)['images']), 3)
        self.assertEqual(len(report['hashes']), 2)

    def test_unannotated_not_zero_annotation(self):
        Image.new('L', (20, 10)).save(self.root / 'a.png')
        report = audit_split(self.root, [])
        self.assertEqual(report['unannotated_images'], ['a.png'])
        self.assertEqual(report['empty_annotation_records'], [])
        self.assertEqual(duplicate_report({'train': report})['status'], 'not_run')

    def test_exact_duplicates_across_splits(self):
        report = {'hashing_enabled': True, 'hashes': {'a.png': 'same', 'b.png': 'same'}}
        duplicate = duplicate_report({'train': report, 'test': report})
        self.assertEqual(len(duplicate['cross_split']), 1)
        self.assertEqual(len(duplicate['cross_split'][0]), 4)
        self.assertEqual(len(duplicate_report({'train': report})['within_split']), 1)

    def test_plot_coordinates(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        Image.new('L', (20, 10)).save(self.root / 'a.png')
        sample = load_coco(self.label, bbox_format='xywh')[0]
        figure = plot_sample(self.root / 'a.png', sample)
        self.assertEqual(figure.axes[0].patches[0].get_xy(), (2, 3))
        self.assertEqual(figure.axes[0].patches[0].get_width(), 4)
        plt.close(figure)

    def test_config_requires_confirmation(self):
        with self.assertRaises(ValueError):
            run_exploration(self.root, {'splits': {}})

    def test_pipeline_reports_partial_annotation_failure(self):
        Image.new('L', (20, 10)).save(self.root / 'a.png')
        config = {'schema_confirmed': True, 'dataset_version': '1.2.1', 'bbox_format': 'xywh',
                  'splits': {'train': {'format': 'coco', 'images': '.', 'annotations': 'labels.json'}}}
        result, _ = run_exploration(self.root, config)
        self.assertTrue(result['splits']['train']['complete'])
        self.label.write_text('{invalid')
        result, _ = run_exploration(self.root, config)
        self.assertFalse(result['splits']['train']['complete'])
        self.assertEqual(len(result['splits']['train']['annotation_errors']), 1)

    def test_safe_paths(self):
        for name in ('../a', '/tmp/a', 'C:/a', 'x\\a', ''):
            with self.assertRaises(ValueError):
                safe_relative(name)

    def test_zip_integrity_limits_and_extraction(self):
        archive = self.root / 'data.zip'
        with ZipFile(archive, 'w') as stream:
            stream.writestr('nested/a.txt', 'hello')
        with self.assertRaises(ValueError):
            inspect_zip(archive, max_unpacked_bytes=1)
        self.assertEqual(len(inspect_zip(archive, max_unpacked_bytes=100)), 1)
        with self.assertRaises(PermissionError):
            extract_zip(archive, self.root / 'unpacked', max_unpacked_bytes=100)
        extract_zip(archive, self.root / 'unpacked', approved=True, max_unpacked_bytes=100)
        self.assertEqual((self.root / 'unpacked/nested/a.txt').read_text(), 'hello')
        with self.assertRaises(FileExistsError):
            extract_zip(archive, self.root / 'unpacked', approved=True, max_unpacked_bytes=100)

    def test_zip_traversal_blocked(self):
        archive = self.root / 'bad.zip'
        with ZipFile(archive, 'w') as stream:
            stream.writestr('../escape.txt', 'bad')
        with self.assertRaises(ValueError):
            extract_zip(archive, self.root / 'bad', approved=True, max_unpacked_bytes=100)
        self.assertFalse((self.root / 'bad').exists())

    def test_download_is_opt_in(self):
        with patch('src.data.download.urlopen') as request:
            with self.assertRaises(PermissionError):
                download_zenodo_file({}, 'x', self.root / 'x.zip', max_bytes=100)
            request.assert_not_called()

    def metadata(self, content):
        import hashlib
        return {'id': 123, 'metadata': {'title': 'HIT-UAV', 'version': '1.2.1', 'license': {'id': 'test-only'}},
                'files': [{'key': 'x.zip', 'size': len(content),
                           'checksum': 'md5:' + hashlib.md5(content).hexdigest(),
                           'links': {'self': 'https://zenodo.org/records/123/files/x.zip'}}]}

    def test_download_checksum_and_manifest(self):
        content = b'test archive bytes'
        with patch('src.data.download.urlopen', return_value=io.BytesIO(content)):
            manifest = download_zenodo_file(self.metadata(content), 'x.zip', self.root / 'x.zip',
                                            approved=True, max_bytes=100)
        self.assertEqual(manifest['sha256'], file_digest(self.root / 'x.zip'))
        self.assertTrue((self.root / 'x.zip.manifest.json').exists())

    def test_download_mismatch_cleans_partial(self):
        metadata = self.metadata(b'good')
        with patch('src.data.download.urlopen', return_value=io.BytesIO(b'evil')):
            with self.assertRaises(ValueError):
                download_zenodo_file(metadata, 'x.zip', self.root / 'x.zip', approved=True, max_bytes=100)
        self.assertFalse((self.root / 'x.zip.part').exists())
        self.assertFalse((self.root / 'x.zip').exists())

    def test_wrong_zenodo_version_blocked(self):
        metadata = self.metadata(b'x')
        metadata['metadata']['version'] = '9.9.9'
        with patch('src.data.download.urlopen', return_value=io.BytesIO(json.dumps(metadata).encode())):
            with self.assertRaises(ValueError):
                zenodo_metadata('123')


if __name__ == '__main__':
    unittest.main()
