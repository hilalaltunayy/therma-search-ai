"""Notebook 02: sentetik ZIP ile baştan sona doğrulama; Drive/ağ kullanılmaz."""
import json
from io import BytesIO
from zipfile import ZipFile

from PIL import Image
from pathlib import Path
import sys
import tempfile

import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_hit_uav import make_archive
from validate_notebook import execute


def validate():
    notebook = nbformat.read(ROOT / 'notebooks/02_hit_uav_real_audit.ipynb', as_version=4)
    nbformat.validate(notebook)
    output = ROOT / 'outputs/validation/real_audit_synthetic'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        original = make_archive(Path(folder) / 'original.zip')
        archive = Path(folder) / 'synthetic.zip'
        # Farklı piksel içerikli tekdüze bir görüntü: dHash=0 yanlış-benzerlik adayı.
        buffer = BytesIO()
        Image.new('L', (640, 512), 120).save(buffer, format='PNG')
        with ZipFile(original) as source, ZipFile(archive, 'w') as target:
            for member in source.namelist():
                content = buffer.getvalue() if member.endswith('/train/negative.png') else source.read(member)
                target.writestr(member, content)
        notebook.cells.insert(0, nbformat.v4.new_markdown_cell(
            '# SENTETİK DOĞRULAMA — gerçek HIT-UAV bulgusu değildir\n'
            'Drive bağlantısı ve public kod bootstrap adımı bu yerel testte atlanır.'))
        notebook.cells.insert(1, nbformat.v4.new_code_cell(
            f"import os\nos.environ['THERMA_CODE_ROOT'] = {str(ROOT)!r}\n"
            f"os.environ['THERMA_ZIP_PATH'] = {str(archive)!r}\n"
            f"os.environ['THERMA_REPORT_ROOT'] = {str(output)!r}"))
        notebook.cells.append(nbformat.v4.new_code_cell(
            "assert all(item['image_files'] == 2 for item in REPORT['splits'].values())\n"
            "assert all(item['objects_by_class_raw']['Person'] == 1 for item in REPORT['splits'].values())\n"
            "assert all(item['objects_by_class_raw']['DontCare'] == 1 for item in REPORT['splits'].values())\n"
            "assert metadata['status'] == 'complete'\n"
            "assert len(metadata['selected_samples']) == 3\n"
            "assert LEAKAGE_SUMMARY['scanned_images'] == 6\n"
            "assert LEAKAGE_SUMMARY['comparison']['exact_pairs'] == 8\n"
            "assert LEAKAGE_SUMMARY['comparison']['near_candidate_pairs'] == 4\n"
            "assert LEAKAGE_SUMMARY['zero_raw_annotation_counts'] == {'train': 1, 'val': 1, 'test': 1}\n"
            "assert LEAKAGE_SUMMARY['manual_review_rows'] == 3\n"
            "assert LEAKAGE_SUMMARY['status'] == 'complete'\n"
            "print('REVIEW_RUN_DIR=' + str(REVIEW_RUN_DIR))\n"
            "print('TEST_RUN_DIR=' + str(RUN_DIR))\n"
            "print('SYNTHETIC_ASSERTIONS_PASSED')"))
        execute(notebook)
        nbformat.write(notebook, output / '02_synthetic.executed.ipynb')
        text = ''.join(o.get('text', '') for c in notebook.cells for o in c.get('outputs', []))
        assert 'SYNTHETIC_ASSERTIONS_PASSED' in text
        figures = [o for c in notebook.cells for o in c.get('outputs', []) if 'image/png' in o.get('data', {})]
        assert len(figures) == 12  # Eski 5 + 3 contact sheet + 2 exact/2 near önizleme.
        run_dir = Path(next(line.split('=', 1)[1] for line in text.splitlines() if line.startswith('TEST_RUN_DIR=')))
        metadata = json.loads((run_dir / 'analysis_metadata.json').read_text())
        assert len(metadata['outputs']) == 7
        assert len(list(run_dir.glob('*.png'))) == 5
        review_dir = Path(next(line.split('=', 1)[1] for line in text.splitlines() if line.startswith('REVIEW_RUN_DIR=')))
        assert len(list(review_dir.glob('contact_sheet_*.png'))) == 3
        assert len(list(review_dir.glob('suspicious_pair_*.png'))) == 12
        summary = json.loads((review_dir / 'leakage_summary.json').read_text())
        assert summary['comparison']['near_pairs_reported'] == 4
        import csv
        with (review_dir / 'manual_review.csv').open(encoding='utf-8-sig') as stream:
            assert all(row['human_present'] == '' for row in csv.DictReader(stream))
    print('PASS: Notebook 02 tüm hücreler; temel 5 PNG/CSV/JSON + contact sheet/manüel CSV + 8 exact ve 4 near aday doğrulandı.')
    print('Gerçek arşiv/Colab Drive/uzak kod bootstrap bu testte sınanmadı.')
    print('Görsel inceleme çıktıları:', run_dir, review_dir)


if __name__ == '__main__':
    validate()
