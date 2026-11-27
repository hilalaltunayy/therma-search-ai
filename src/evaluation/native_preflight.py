"""Read-only Phase 06 native JSON validation. No model, dataset or inference is loaded.

Run: python -m src.evaluation.native_preflight RUN_DIRECTORY
or:  python -m src.evaluation.native_preflight --latest-in REPORT_ROOT
"""
import argparse
import json
from pathlib import Path

from src.data.audit import file_digest
from .error_analysis import load_native_predictions, NATIVE_PERSON_CATEGORY_TO_CLASS


def latest_native_run(report_root, *, required=True):
    """Newest known Phase 06 export with a copied data manifest; no fallback on invalid IDs."""
    candidates=[p.parent.parent for p in Path(report_root).glob('run_phase06_*/native_val/predictions.json')
                if (p.parent.parent/'dataset_manifest.json').is_file()]
    if not candidates:
        if required: raise FileNotFoundError('No previous native JSON + dataset_manifest.json found in report root.')
        return None
    return max(candidates,key=lambda p:((p/'native_val/predictions.json').stat().st_mtime_ns,p.name))


def preflight_native_export(run_directory):
    """Parse existing exported predictions using the same loader as the full analysis.

    Uses copied manifest metadata, so Colab's old temporary images are unnecessary.
    Returns counts/hashes only; it does not recompute or overwrite evaluation metrics.
    """
    root=Path(run_directory).resolve()
    manifest_path=root/'dataset_manifest.json'
    prediction_path=root/'native_val/predictions.json'
    for path in (manifest_path,prediction_path):
        if not path.is_file(): raise FileNotFoundError(f'Preflight input missing: {path}')
    before={str(p.relative_to(root)):file_digest(p) for p in (manifest_path,prediction_path)}
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('status')!='ready' or not isinstance(manifest.get('images'),list):
        raise ValueError('A ready, copied data manifest is required for preflight.')
    rows=[]
    for row in manifest['images']:
        if row['disposition']=='included' and row['split']=='val':
            rows.append({'member':row['source_member'],'image_path':row['image_path'],
                         'width':row['width'],'height':row['height']})
    if not rows: raise ValueError('No included original validation images in manifest.')
    parsed=load_native_predictions(prediction_path,rows)
    after={str(p.relative_to(root)):file_digest(p) for p in (manifest_path,prediction_path)}
    if before!=after: raise ValueError('Preflight inputs changed during the read-only check.')
    return {'status':'passed','run_directory':str(root),'read_only':True,'model_loaded':False,
            'ultralytics_export_contract':'8.3.228 non-COCO single Person',
            'native_category_to_internal_class':NATIVE_PERSON_CATEGORY_TO_CLASS,
            'validation_images':len(rows),'native_predictions':sum(len(v) for v in parsed.values()),
            'images_with_native_predictions':sum(bool(v) for v in parsed.values()),
            'input_sha256':before,'inputs_unchanged':True,
            'scope':'Parser validation only; no model inference, checkpoint loading or metric recomputation.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('run_directory',nargs='?')
    group.add_argument('--latest-in',type=Path,metavar='REPORT_ROOT')
    args=parser.parse_args()
    run=latest_native_run(args.latest_in) if args.latest_in is not None else args.run_directory
    print(json.dumps(preflight_native_export(run),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
