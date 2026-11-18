"""Notebook 03 bütün hücreler: bilinen sentetik örnek, bilinmeyen ZIP, eksik ZIP.

Public kod bootstrap ve Drive OAuth yerel testte atlanır. Kaynak notebook çıktısızdır.
"""
import json
from pathlib import Path
import sys
import tempfile

import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tests'))
from test_wisard import make_wisard_fixture
from test_wisard_sample import make_sample
from validate_notebook import execute


def validate():
    source = nbformat.read(ROOT/'notebooks/03_wisard_exploration.ipynb', as_version=4)
    nbformat.validate(source)
    assert all(not c.get('outputs') and c.get('execution_count') is None for c in source.cells if c.cell_type == 'code')
    output = ROOT/'outputs/validation/wisard_one_pass'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        known = make_sample(root/'known.zip')
        unknown = make_wisard_fixture(root/'unknown.zip')
        for mode, archive in [('recognized_synthetic', known), ('unknown_synthetic', unknown), ('missing_zip', root/'absent.zip')]:
            nb = nbformat.reads(nbformat.writes(source), as_version=4)
            nb.cells.insert(0, nbformat.v4.new_markdown_cell('# SENTETİK TEST — gerçek WiSARD verisi değildir'))
            nb.cells.insert(1, nbformat.v4.new_code_cell(
                f"import os\nos.environ['THERMA_CODE_ROOT']={str(ROOT)!r}\n"
                f"os.environ['THERMA_WISARD_REPORT_ROOT']={str(output)!r}\n"
                f"os.environ['THERMA_WISARD_ZIP']={str(archive)!r}"))
            checks = {
                'recognized_synthetic': """assert WISARD_SUMMARY['local_image_count']==24
assert WISARD_SUMMARY['modalities']['IR']['person_annotations']==18
assert WISARD_SUMMARY['pairing_candidate_counts']=={'A_same_number':11, 'B_shift_minus_one':12}
assert len(list(WISARD_RUN_DIR.glob('pair_A_*.png')))==10
assert len(list(WISARD_RUN_DIR.glob('pair_B_*.png')))==10
assert WISARD_SUMMARY['status']=='complete_provisional_pairing'
assert WISARD_SUMMARY['problem_file_count']==0""",
                'unknown_synthetic': """assert WISARD_SUMMARY['status']=='unknown_structure'
assert WISARD_SUMMARY['local_image_count']==4
assert not WISARD_SUMMARY['modalities']
assert not list(WISARD_RUN_DIR.glob('*.png'))""",
                'missing_zip': """assert WISARD_SUMMARY['status']=='failed_with_diagnostics'
assert WISARD_SUMMARY['local_image_count'] is None
assert WISARD_SUMMARY['problem_file_count']==1""",
            }
            nb.cells.append(nbformat.v4.new_code_cell(checks[mode]+"\nassert (WISARD_RUN_DIR/'wisard_analysis_report.md').is_file()\nprint('SYNTHETIC_ASSERTIONS_PASSED')"))
            execute(nb)
            nbformat.write(nb, output/f'{mode}.executed.ipynb')
            text = ''.join(o.get('text','') for c in nb.cells for o in c.get('outputs', []))
            assert 'SYNTHETIC_ASSERTIONS_PASSED' in text
            assert 'Kesinleşmeyenler:' in text
            print('PASS: Notebook 03 tüm hücreler:', mode)
    print('Gerçek ZIP/Colab Drive OAuth doğrulanmadı. Çıktılar:', output)


if __name__ == '__main__':
    validate()
