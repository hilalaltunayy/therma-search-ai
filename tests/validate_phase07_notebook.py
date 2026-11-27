"""Notebook 07 top-to-bottom synthetic preparation; GPU probe mocked, no training."""
import json
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient.exceptions import CellExecutionError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_phase07 import make_phase07_baseline
from validate_notebook import execute


def validate():
    source=nbformat.read(ROOT/'notebooks/07_hit_uav_controlled_training.ipynb',as_version=4)
    nbformat.validate(source)
    assert all(not c.get('outputs') and c.get('execution_count') is None for c in source.cells if c.cell_type=='code')
    out=ROOT/'outputs/validation/phase07';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);baseline,archive=make_phase07_baseline(root)
        for mode in ('synthetic_preparation','no_gpu','missing_baseline'):
            nb=nbformat.reads(nbformat.writes(source),as_version=4)
            env=nbformat.v4.new_code_cell(f'''import os,sys
os.environ['THERMA_CODE_ROOT']={str(ROOT)!r}
os.environ['THERMA_PHASE07_BASELINE']={str(root/'missing' if mode=='missing_baseline' else baseline)!r}
os.environ['THERMA_PHASE07_HIT_ZIP']={str(archive)!r}
os.environ['THERMA_PHASE07_OUTPUT']={str(root/mode)!r}
os.environ['THERMA_PHASE07_WORK']={str(root/'work')!r}
os.environ.pop('THERMA_PHASE07_BLOCK',None)
sys.path.insert(0,{str(ROOT/'tests')!r})''')
            mock=nbformat.v4.new_code_cell('''from unittest.mock import patch
from test_phase07 import synthetic_runtime,synthetic_probe
PROBE_CALLS=[]
def tracked_probe(*args):
    PROBE_CALLS.append(args[-1])
    return synthetic_probe(*args)
PATCHES=[patch('src.training.phase07_runtime.runtime_identity',synthetic_runtime),
         patch('src.training.phase07_runtime.probe_training_memory',tracked_probe)]
for item in PATCHES: item.start()
print('SYNTHETIC PREPARATION: GPU feasibility mocked; no real memory/model performance measured.')''')
            if mode=='no_gpu':
                mock.source+='''\npatch('src.training.phase07_runtime.runtime_identity',side_effect=RuntimeError('SYNTHETIC no GPU')).start()'''
            nb.cells=[nbformat.v4.new_markdown_cell('# SYNTHETIC VALIDATION — no real training'),env,*nb.cells[:3],mock,*nb.cells[3:]]
            if mode!='missing_baseline':
                nb.cells.append(nbformat.v4.new_code_cell(f'''assert ENABLE_TRAINING is False
assert PLAN['training_executed'] is False
assert (PHASE07_BLOCK/'preparation_report.md').is_file()
assert MEMORY_PREFLIGHT['status']=={'blocked' if mode=='no_gpu' else 'passed'!r}
assert len(PROBE_CALLS)=={0 if mode=='no_gpu' else 4}
assert not list(PHASE07_BLOCK.glob('*/attempts/*'))
print('SYNTHETIC_PHASE07_ASSERTIONS_PASSED')'''))
            try: execute(nb)
            except CellExecutionError as exc:
                if mode!='missing_baseline': raise
                assert 'FileNotFoundError' in str(exc)
                status=json.loads(next((root/mode).glob('*/preparation_status.json')).read_text())
                assert status['status']=='blocked'
            else: assert mode!='missing_baseline'
            nbformat.write(nb,out/f'{mode}.executed.ipynb')
            print('PASS: Notebook 07',mode)
    print('Real GPU/model memory feasibility and actual training were not executed.')


if __name__=='__main__': validate()
