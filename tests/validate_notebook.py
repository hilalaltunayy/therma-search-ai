"""Notebook'u ağ/indirme kapalı olarak iki modda çalıştırır; gerçek veri kullanmaz.

Çalıştırma: python tests/validate_notebook.py
Varsayılan notebook çıktısı ve sentetik çalıştırma outputs/validation altında kalır.
Kaynak notebook'a yürütme çıktısı yazılmaz.
"""
import base64
import json
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_data import coco_fixture


def execute(nb):
    client = NotebookClient(nb, timeout=90, resources={'metadata': {'path': str(ROOT)}})
    client.km = KernelManager(kernel_name='python3', transport='ipc')
    client.km.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
    client.execute()
    return nb


def validate():
    path = ROOT / 'notebooks/01_hit_uav_exploration.ipynb'
    source = nbformat.read(path, as_version=4)
    nbformat.validate(source)
    output = ROOT / 'outputs/validation'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        # Dış ortam değişkenlerinden bağımsız, veri bulunmayan varsayılan mod.
        default = nbformat.reads(nbformat.writes(source), as_version=4)
        default.cells.insert(0, nbformat.v4.new_code_cell(
            f"import os\nos.environ['THERMA_DATA_ROOT'] = {str(temporary / 'absent')!r}\n"
            f"os.environ['THERMA_CONFIG_PATH'] = {str(ROOT / 'configs/hit_uav.example.json')!r}"))
        execute(default)
        nbformat.write(default, output / 'default_no_data.executed.ipynb')
        text = ''.join(o.get('text', '') for c in default.cells for o in c.get('outputs', []))
        assert 'İndirme yapılmadı.' in text and 'Analiz yapılmadı:' in text
        print('PASS: notebook şeması + veri bulunmayan varsayılan akış; indirme kapalı.')

        splits = {}
        for split in ('train', 'validation', 'test'):
            folder = temporary / split
            folder.mkdir()
            Image.new('L', (20, 10), color=120).save(folder / 'a.png')
            Image.new('L', (20, 10)).save(folder / 'negative.png')
            (folder / 'annotations.json').write_text(json.dumps(coco_fixture()))
            splits[split] = {'format': 'coco', 'images': split, 'annotations': split + '/annotations.json'}
        config = {'dataset_version': '1.2.1', 'schema_confirmed': True,
                  'bbox_format': 'xywh', 'coordinate_origin': None, 'splits': splits}
        config_path = temporary / 'config.json'
        config_path.write_text(json.dumps(config))
        synthetic = nbformat.reads(nbformat.writes(source), as_version=4)
        synthetic.cells.insert(0, nbformat.v4.new_markdown_cell(
            '# SENTETİK TEST ÇIKTISI — gerçek HIT-UAV verisi değildir\n'
            'Bu çalıştırmadaki istatistikler yalnızca yapay test dosyalarına aittir.'))
        synthetic.cells.insert(1, nbformat.v4.new_code_cell(
            f"import os\nos.environ['THERMA_DATA_ROOT'] = {str(temporary)!r}\n"
            f"os.environ['THERMA_CONFIG_PATH'] = {str(config_path)!r}"))
        execute(synthetic)
        nbformat.write(synthetic, output / 'synthetic_only.executed.ipynb')
        figures = [o['data']['image/png'] for c in synthetic.cells for o in c.get('outputs', [])
                   if 'image/png' in o.get('data', {})]
        assert len(figures) >= 9, f'Grafik/kutu çıktıları eksik: {len(figures)}'
        for index in (0, 1, 6):
            (output / f'synthetic_figure_{index}.png').write_bytes(base64.b64decode(figures[index]))
        text = ''.join(o.get('text', '') for c in synthetic.cells for o in c.get('outputs', []))
        assert "'Person': 1" in text and "'DontCare': 1" in text
        assert 'annotation_errors adet: 0' in text
        print(f'PASS: sentetik 3 split üzerinde tüm hücreler; {len(figures)} grafik/görsel çıktısı.')
    print('Gerçek veri ve canlı indirme doğrulanmadı. Çıktılar:', output)


if __name__ == '__main__':
    validate()
