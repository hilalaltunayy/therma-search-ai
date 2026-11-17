"""Notebook 03: arşivsiz, kuralsız ZIP ve onaylı sentetik kural akışları; Drive/ağ yok."""
from pathlib import Path
import sys
import tempfile

import nbformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from test_wisard import make_wisard_fixture, pairing_fixture, label_fixture
from validate_notebook import execute


def validate():
    source = nbformat.read(ROOT/'notebooks/03_wisard_exploration.ipynb',as_version=4)
    nbformat.validate(source)
    output = ROOT/'outputs/validation/wisard'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        archive = make_wisard_fixture(root/'WiSARD_sample.zip')
        for mode in ('source_only','inspect_unconfirmed','confirmed_synthetic'):
            nb = nbformat.reads(nbformat.writes(source),as_version=4)
            nb.cells.insert(0,nbformat.v4.new_markdown_cell(
                '# SENTETİK DOĞRULAMA — gerçek WiSARD verisi değildir\n'
                'Public kod kurulumu ve Drive bağlantısı bu yerel doğrulamada atlanır.'))
            nb.cells.insert(1,nbformat.v4.new_code_cell(
                f"import os\nos.environ['THERMA_CODE_ROOT']={str(ROOT)!r}\n"
                f"os.environ['THERMA_WISARD_DATA_DIR']={str(root/'no_archives')!r}\n"
                f"os.environ['THERMA_WISARD_REPORT_ROOT']={str(output)!r}\n"
                f"os.environ['THERMA_WISARD_ZIP']={'' if mode=='source_only' else str(archive)!r}"))
            if mode=='confirmed_synthetic':
                for cell in nb.cells:
                    if cell.cell_type=='code' and cell.source.startswith('PAIRING_SPEC ='):
                        cell.source=f'PAIRING_SPEC = {pairing_fixture()!r}\nLABEL_SPEC = {label_fixture()!r}\nMAX_PREVIEWS=3\nEXTRA_PREVIEW_MEMBERS=[]'
            expected = "assert WISARD_SUMMARY['status']=='source_only'\nassert WISARD_SUMMARY['local_image_count'] is None" if mode=='source_only' else (
                "assert WISARD_SUMMARY['local_image_count']==4\n" +
                ("assert WISARD_SUMMARY['pair_count']==2\nassert WISARD_SUMMARY['class_counts']=={'Person':2}\nassert len(list(WISARD_RUN_DIR.glob('*.png')))==5"
                 if mode=='confirmed_synthetic' else
                 "assert WISARD_SUMMARY['pair_count'] is None\nassert WISARD_SUMMARY['class_counts'] is None\nassert not list(WISARD_RUN_DIR.glob('*.png'))"))
            nb.cells.append(nbformat.v4.new_code_cell(expected+"\nprint('WISARD_RUN_DIR='+str(WISARD_RUN_DIR))\nprint('SYNTHETIC_ASSERTIONS_PASSED')"))
            execute(nb)
            nbformat.write(nb,output/f'{mode}.executed.ipynb')
            text=''.join(o.get('text','') for c in nb.cells for o in c.get('outputs',[]))
            assert 'SYNTHETIC_ASSERTIONS_PASSED' in text
            figures=[o for c in nb.cells for o in c.get('outputs',[]) if 'image/png' in o.get('data',{})]
            assert len(figures)==(5 if mode=='confirmed_synthetic' else 0)
            print('PASS: WiSARD Notebook 03',mode)
            print(next(line for line in text.splitlines() if line.startswith('WISARD_RUN_DIR=')))
    print('Gerçek WiSARD ZIP, lisans, Drive OAuth veya gerçek eşleştirme/etiket şeması doğrulanmadı.')


if __name__=='__main__':
    validate()
