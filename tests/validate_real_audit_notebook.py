"""Notebook 02: sentetik ZIP ile baştan sona doğrulama; Drive/ağ kullanılmaz."""
import json
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
        archive = make_archive(Path(folder) / 'synthetic.zip')
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
            "print('TEST_RUN_DIR=' + str(RUN_DIR))\n"
            "print('SYNTHETIC_ASSERTIONS_PASSED')"))
        execute(notebook)
        nbformat.write(notebook, output / '02_synthetic.executed.ipynb')
        text = ''.join(o.get('text', '') for c in notebook.cells for o in c.get('outputs', []))
        assert 'SYNTHETIC_ASSERTIONS_PASSED' in text
        figures = [o for c in notebook.cells for o in c.get('outputs', []) if 'image/png' in o.get('data', {})]
        assert len(figures) == 5
        run_dir = Path(next(line.split('=', 1)[1] for line in text.splitlines() if line.startswith('TEST_RUN_DIR=')))
        metadata = json.loads((run_dir / 'analysis_metadata.json').read_text())
        assert len(metadata['outputs']) == 7
        assert len(list(run_dir.glob('*.png'))) == 5
    print('PASS: notebook 02 şeması + tüm hücreler + sentetik 3 split + 5 PNG + CSV/JSON/metadata.')
    print('Gerçek arşiv/Colab Drive/uzak kod bootstrap bu testte sınanmadı.')
    print('Görsel inceleme çıktıları:', run_dir)


if __name__ == '__main__':
    validate()
