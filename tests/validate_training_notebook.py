"""Notebook 04 tüm hücreleri: sentetik ZIP ve sahte GPU/YOLO; gerçek eğitim yok."""
from pathlib import Path
import sys
import tempfile
import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_yolo_training import make_training_fixture
from validate_notebook import execute


def validate():
    notebook = nbformat.read(ROOT/'notebooks/04_hit_uav_yolo_training.ipynb', as_version=4)
    nbformat.validate(notebook)
    assert all(not c.get('outputs') and c.get('execution_count') is None for c in notebook.cells if c.cell_type == 'code')
    out = ROOT/'outputs/validation/yolo_training'
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        archive=make_training_fixture(root/'synthetic.zip')
        env = nbformat.v4.new_code_cell(
            f"import os, sys\nos.environ['THERMA_CODE_ROOT']={str(ROOT)!r}\n"
            f"os.environ['THERMA_TRAIN_ZIP']={str(archive)!r}\n"
            f"os.environ['THERMA_TRAIN_OUTPUT']={str(out)!r}\n"
            f"os.environ['THERMA_TRAIN_WORK']={str(root/'work')!r}\n"
            f"sys.path.insert(0,{str(ROOT/'tests')!r})")
        mocks = nbformat.v4.new_code_cell('''from unittest.mock import patch
from test_yolo_training import fake_runtime, fake_modules, FakeYOLO
runtime_patch = fake_runtime()
runtime_patch.start()
modules_patch = patch.dict('sys.modules', fake_modules())
modules_patch.start()
FakeYOLO.calls = []
FakeYOLO.fail_train = False
print('SENTETİK: model, metrikler ve GPU sahtedir; gerçek eğitim yapılmaz.')''')
        notebook.cells = [nbformat.v4.new_markdown_cell('# SENTETİK TEST — gerçek eğitim/model başarımı değildir'), env, *notebook.cells[:3], mocks, *notebook.cells[3:]]
        notebook.cells.append(nbformat.v4.new_code_cell('''assert TRAIN_SUMMARY['status']=='complete_exploratory_baseline'
assert TRAIN_SUMMARY['test_used_for_selection'] is False
assert (TRAIN_RUN_DIR/'best.pt').read_bytes()==b'SYNTHETIC, NOT A MODEL'
assert TRAIN_SUMMARY['test_fixed_threshold']['images']==2
assert (TRAIN_RUN_DIR/'training_report.md').exists()
assert len([x for x in FakeYOLO.calls if x[0]=='val'])==1
print('SYNTHETIC_NOTEBOOK_ASSERTIONS_PASSED')
modules_patch.stop()
runtime_patch.stop()'''))
        execute(notebook)
        nbformat.write(notebook, out/'synthetic_only.executed.ipynb')
    print('PASS: Notebook 04 şeması ve tüm hücreler, sentetik dönüşüm + mocked train/best/test; gerçek GPU/eğitim yok.')


if __name__=='__main__':
    validate()
