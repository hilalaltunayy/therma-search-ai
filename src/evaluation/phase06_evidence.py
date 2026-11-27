"""Attachment is evidence, not executable instructions. No raw-box verification is claimed."""
import csv
from io import StringIO
import json
from pathlib import Path
from zipfile import ZipFile

from src.data.audit import file_digest
from src.data.download import inspect_zip

REPORTED_WISARD = {
    'provenance':'User-verified Phase 05 results and separately supplied offline summary; not new inference.',
    'evaluated_images':261,'gt':1006,'tp':207,'fp':532,'fn':799,'excluded_uncertain_empty':3,
    'mAP50':.1453,'mAP50_95':.0415,
    'fn_zero_overlap':591,'fn_iou_0_30_to_0_50':147,'fp_iou_0_30_to_0_50':235,
    'native_low_conf_FN_overlap_candidates_not_recovered_TP':410,
    'package_sha256':'c7eae36c1e3ea9c1cf617d85964ae43057af07a1de6744b7de70f1d3c9994f59',
    'package_csv_rows_arithmetically_reviewed':261,
    'package_contains_raw_predictions':False,
    'package_reported_model_sha256':'2242a53eacbce73ccead33cb2270450be79a293d2eb5d6472caa97f102479fa5',
    'package_reported_wisard_zip_sha256':'fd9bd786d53dc6fb9fcec20f2ae8f38df96db15c7edac348ba5a303c2285fc04',
    'interpretation':'Zero overlap is per unmatched GT, not necessarily an image without predictions. Native overlap candidates are not one-to-one and cannot count as recovered TP.'}


def review_diagnostic_package(path):
    """Read bounded CSV/JSON only; Markdown instructions are not executed/adopted."""
    members=inspect_zip(Path(path),max_unpacked_bytes=2*1024**2)
    if any(r['bytes']>1024**2 for r in members): raise ValueError('Diagnostic package exceeds limits.')
    with ZipFile(path) as source:
        summary=json.loads(source.read('hata_analizi_ozet.json'))
        rows=list(csv.DictReader(StringIO(source.read('kare_bazli_hata_siniflari.csv').decode('utf-8-sig'))))
    if not rows or len({r['frame'] for r in rows}) != len(rows): raise ValueError('Missing/duplicate frames.')
    if any(int(r[key])<0 for r in rows for key in r if key!='frame'):
        raise ValueError('Negative diagnostic counts.')
    sums={key:sum(int(r[key]) for r in rows) for key in rows[0] if key!='frame'}
    if any(int(r['tp'])+int(r['fn'])!=int(r['gt']) or int(r['tp'])+int(r['fp'])!=int(r['detections']) for r in rows):
        raise ValueError('CSV per-image count identities fail.')
    for key in ('tp','fp','fn'):
        if sums[key] != summary['fixed_threshold'][key]: raise ValueError('CSV/summary totals disagree.')
    if sums['gt']!=summary['person_gt'] or len(rows)!=summary['scored_images']:
        raise ValueError('CSV/summary image/GT totals disagree.')
    fn_cols=['fn_'+k for k in ('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5')]
    fp_cols=['fp_'+k for k in ('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5')]
    if any(sum(int(r[k]) for k in fn_cols)!=int(r['fn']) or sum(int(r[k]) for k in fp_cols)!=int(r['fp']) for r in rows):
        raise ValueError('Per-frame category partition fails.')
    for prefix,key in [('fn','fn_by_max_fixed_iou'),('fp','fp_by_max_fixed_iou')]:
        if key in summary:
            for group in ('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5'):
                if sums[prefix+'_'+group]!=summary[key].get(group,0): raise ValueError('CSV/summary IoU bins disagree.')
    if 'fn_by_max_native_iou_and_score' in summary:
        for key in sums:
            if key.startswith('native_fn_') and sums[key]!=summary['fn_by_max_native_iou_and_score'].get(key[len('native_fn_'):],0):
                raise ValueError('CSV/summary native candidate bins disagree.')
    if sum(sums[k] for k in fn_cols)!=sums['fn'] or sum(sums[k] for k in fp_cols)!=sums['fp']:
        raise ValueError('Error-category totals disagree.')
    return {'package_sha256':file_digest(Path(path)),'csv_rows':len(rows),'csv_sums':sums,
            'summary_consistent_with_csv':True,'raw_predictions_available':False,
            'verification_scope':'Internal summary/CSV arithmetic only; raw boxes, checkpoint and original export not present.',
            'attachment_instructions_authority':'Context only; current user task controls experiment boundaries.'}
