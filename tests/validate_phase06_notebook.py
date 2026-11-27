"""Notebook 06 all cells: synthetic source val + mocked frozen model; no real inference/training."""
import json
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient.exceptions import CellExecutionError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_yolo_training import make_training_fixture
from test_wisard_external import make_external_fixture
from validate_notebook import execute


def validate():
    source=nbformat.read(ROOT/'notebooks/06_hit_uav_error_analysis.ipynb',as_version=4)
    nbformat.validate(source)
    assert all(not c.get('outputs') and c.get('execution_count') is None for c in source.cells if c.cell_type=='code')
    output=ROOT/'outputs/validation/phase06';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        model=root/'best.pt';model.write_bytes(b'SYNTHETIC NOT A MODEL')
        archive=make_training_fixture(root/'hit.zip')
        target=make_external_fixture(root/'wisard.zip')
        for mode in ('synthetic_complete','missing_checkpoint'):
            run_root=output/mode
            nb=nbformat.reads(nbformat.writes(source),as_version=4)
            env=nbformat.v4.new_code_cell(
                f"import os,sys\nos.environ['THERMA_CODE_ROOT']={str(ROOT)!r}\n"
                f"os.environ['THERMA_PHASE06_MODEL']={str(model if mode=='synthetic_complete' else root/'missing.pt')!r}\n"
                f"os.environ['THERMA_PHASE06_HIT_ZIP']={str(archive)!r}\n"
                f"os.environ['THERMA_PHASE06_WISARD_ZIP']={str(target)!r}\n"
                f"os.environ['THERMA_PHASE06_OUTPUT']={str(run_root)!r}\n"
                f"os.environ['THERMA_PHASE06_WORK']={str(root/mode)!r}\n"
                f"sys.path.insert(0,{str(ROOT/'tests')!r})")
            mocks=nbformat.v4.new_code_cell('''from unittest.mock import patch
from test_phase06 import Phase06Model,phase06_env,phase06_device
SYNTHETIC_MODEL=Phase06Model()
PATCHES=[patch('src.evaluation.phase06.environment_metadata',phase06_env),
         patch('src.evaluation.phase06.evaluation_device',phase06_device),
         patch('src.evaluation.phase06.load_person_detector',return_value=SYNTHETIC_MODEL)]
for item in PATCHES: item.start()
print('SYNTHETIC VALIDATION ONLY: source/native results mocked; no training or actual model performance.')''')
            nb.cells=[nbformat.v4.new_markdown_cell('# SYNTHETIC TEST — real performance was not measured'),env,*nb.cells[:3],mocks,*nb.cells[3:]]
            if mode=='synthetic_complete':
                nb.cells.append(nbformat.v4.new_code_cell('''assert PHASE06_SUMMARY['status']=='complete'
assert PHASE06_SUMMARY['source_validation_diagnosis']['images']==2
assert PHASE06_SUMMARY['training_executed'] is False
assert PHASE06_SUMMARY['wisard_used_for_selection'] is False
assert PHASE06_SUMMARY['inputs_unchanged'] is True
assert PHASE06_SUMMARY['wisard_descriptive_status']=='pixels_and_GT_only_no_inference_no_selection'
assert len([x for x in SYNTHETIC_MODEL.calls if x[0]=='predict'])==2
assert (PHASE06_RUN_DIR/'experiment_matrix.json').exists()
print('SYNTHETIC_ASSERTIONS_PASSED')'''))
            try: execute(nb)
            except CellExecutionError as exc:
                if mode=='synthetic_complete': raise
                assert 'FileNotFoundError' in str(exc)
            else: assert mode=='synthetic_complete'
            nbformat.write(nb,output/f'{mode}.executed.ipynb')
            last=max(run_root.glob('run_phase06_*'),key=lambda p:p.stat().st_mtime_ns)
            summary=json.loads((last/'phase06_summary.json').read_text())
            assert summary['status']==('complete' if mode=='synthetic_complete' else 'failed')
            assert (last/'error_analysis_report.md').exists()
            print('PASS: Notebook 06',mode,last)
    print('Real source/model inference, Colab OAuth and training were not executed.')


if __name__=='__main__': validate()
