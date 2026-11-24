"""Notebook 05: synthetic IR data + mocked frozen model; never real model performance."""
import json
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient.exceptions import CellExecutionError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_wisard_external import make_external_fixture
from validate_notebook import execute


def validate():
    source=nbformat.read(ROOT/'notebooks/05_wisard_external_evaluation.ipynb',as_version=4)
    nbformat.validate(source)
    assert all(not c.get('outputs') and c.get('execution_count') is None for c in source.cells if c.cell_type=='code')
    output=ROOT/'outputs/validation/wisard_external'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        model=root/'synthetic_best.pt'
        model.write_bytes(b'SYNTHETIC ONLY, NOT A MODEL')
        archive=make_external_fixture(root/'sample.zip')
        malformed=make_external_fixture(root/'bad.zip',{1:'0 nan .5 .1 .1'})
        for mode in ('synthetic_complete','missing_checkpoint','malformed_IR'):
            nb=nbformat.reads(nbformat.writes(source),as_version=4)
            run_root=output/mode
            checkpoint=root/'missing.pt' if mode=='missing_checkpoint' else model
            data=malformed if mode=='malformed_IR' else archive
            env=nbformat.v4.new_code_cell(
                f"import os, sys\nos.environ['THERMA_CODE_ROOT']={str(ROOT)!r}\n"
                f"os.environ['THERMA_EXTERNAL_MODEL']={str(checkpoint)!r}\n"
                f"os.environ['THERMA_EXTERNAL_ZIP']={str(data)!r}\n"
                f"os.environ['THERMA_EXTERNAL_OUTPUT']={str(run_root)!r}\n"
                f"os.environ['THERMA_EXTERNAL_WORK']={str(root/mode)!r}\n"
                f"sys.path.insert(0,{str(ROOT/'tests')!r})")
            mock=nbformat.v4.new_code_cell('''from unittest.mock import patch
from test_wisard_external import ExternalModelStub, synthetic_environment, synthetic_device
SYNTHETIC_MODEL=ExternalModelStub()
PATCHES=[patch('src.evaluation.wisard_external.environment_metadata',synthetic_environment),
         patch('src.evaluation.wisard_external.evaluation_device',synthetic_device),
         patch('src.evaluation.wisard_external.load_person_detector',return_value=SYNTHETIC_MODEL)]
for item in PATCHES:
    item.start()
print('SYNTHETIC VALIDATION ONLY: model/GPU/metrics are mocks, not actual WiSARD performance.')''')
            nb.cells=[nbformat.v4.new_markdown_cell('# SYNTHETIC VALIDATION — no real checkpoint evaluation'),env,*nb.cells[:3],mock,*nb.cells[3:]]
            if mode=='synthetic_complete':
                nb.cells.append(nbformat.v4.new_code_cell('''assert EXTERNAL_SUMMARY['status']=='complete'
assert EXTERNAL_SUMMARY['coverage']['included_images']==2
assert EXTERNAL_SUMMARY['coverage']['excluded_images']==1
assert EXTERNAL_SUMMARY['fixed_threshold']['tp']==2
assert EXTERNAL_SUMMARY['fixed_threshold']['small_object_recall']['width_lt_16']['recall']==.5
assert EXTERNAL_SUMMARY['inputs_unchanged'] is True
assert len([call for call,args in SYNTHETIC_MODEL.calls if call=='val'])==1
print('SYNTHETIC_ASSERTIONS_PASSED')'''))
            try:
                execute(nb)
            except CellExecutionError as exc:
                if mode=='synthetic_complete':
                    raise
                assert ('FileNotFoundError' if mode=='missing_checkpoint' else 'Malformed/unsupported IR') in str(exc)
            else:
                assert mode=='synthetic_complete'
            nbformat.write(nb,output/f'{mode}.executed.ipynb')
            latest=max(run_root.glob('run_wisard_external_*'),key=lambda p:p.stat().st_mtime_ns)
            summary=json.loads((latest/'evaluation_summary.json').read_text())
            assert summary['status']==('complete' if mode=='synthetic_complete' else 'failed')
            if mode!='synthetic_complete':
                assert summary['fixed_threshold'] is None and summary['ultralytics_map'] is None
            assert (latest/'evaluation_report.md').exists()
            print('PASS: Notebook 05',mode,'outputs:',latest)
    print('Real model/ZIP, Google Drive OAuth and Ultralytics CPU/CUDA inference were NOT executed.')


if __name__=='__main__':
    validate()
