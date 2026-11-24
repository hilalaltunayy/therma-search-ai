"""Sabit eşik tanılaması: mevcut bire bir eşleme, açık GT paydaları ve IoU özeti.

Ultralytics mAP'ı burada yeniden uygulanmaz. Küçük nesneler için yeniden eşleme
çalıştırılmaz; bütün görüntüdeki tek eşlemenin hedef indeksleri kullanılır.
"""
from src.data.wisard_sample import describe
from .person_detection import box_iou

SMALL_GROUPS = ('width_lt_16', 'height_lt_16', 'both_lt_16')


def small_object_recall(targets, matched_target_indices, *, sizes=None):
    matched = set(matched_target_indices)
    if not matched <= set(range(len(targets))):
        raise ValueError('Eşleşen GT indeksi hedef listesi dışında.')
    if sizes is None:
        sizes = [(b[2]-b[0], b[3]-b[1]) for b in targets]
    if len(sizes) != len(targets):
        raise ValueError('GT boyut listesi hedef sayısıyla uyuşmuyor.')
    groups = {k: {'ground_truth_count': 0, 'detected_count': 0} for k in SMALL_GROUPS}
    for i, (w, h) in enumerate(sizes):
        if w <= 0 or h <= 0:
            raise ValueError('GT boyutları pozitif olmalı.')
        conditions = (w < 16, h < 16, w < 16 and h < 16)
        for key, selected in zip(SMALL_GROUPS, conditions):
            if selected:
                groups[key]['ground_truth_count'] += 1
                groups[key]['detected_count'] += i in matched
    for r in groups.values():
        n = r['ground_truth_count']
        r.update(missed_count=n-r['detected_count'], recall=r['detected_count']/n if n else None)
    return groups


def aggregate_fixed_records(records):
    if not records:
        raise ValueError('Skorlanabilir görüntü yok; sıfır başarı metriği üretilmedi.')
    totals = {k: sum(r['matching'][k] for r in records) for k in ('tp', 'fp', 'fn')}
    groups = {k: {'ground_truth_count': 0, 'detected_count': 0} for k in SMALL_GROUPS}
    ious, best_ious, sizes_all = [], [], []
    for row in records:
        matches = row['matching']['matches']
        sizes_all.extend(row.get('ground_truth_sizes_px', [(b[2]-b[0],b[3]-b[1]) for b in row['ground_truth_xyxy']]))
        small = small_object_recall(row['ground_truth_xyxy'], [m['target_index'] for m in matches], sizes=row.get('ground_truth_sizes_px'))
        for key in SMALL_GROUPS:
            for count in ('ground_truth_count', 'detected_count'):
                groups[key][count] += small[key][count]
        ious.extend(m['iou'] for m in matches)
        best_ious.extend(max((box_iou(gt, p['bbox_xyxy']) for p in row['detections']), default=0)
                         for gt in row['ground_truth_xyxy'])
    for r in groups.values():
        n = r['ground_truth_count']
        r.update(missed_count=n-r['detected_count'], recall=r['detected_count']/n if n else None)
    tp, fp, fn = (totals[k] for k in ('tp', 'fp', 'fn'))
    return {**totals, 'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'evaluated_images': len(records), 'ground_truth_person_count': tp+fn,
            'false_positives_per_evaluated_image': fp/len(records),
            'images_with_fp': sum(r['matching']['fp'] > 0 for r in records),
            'images_with_fn': sum(r['matching']['fn'] > 0 for r in records),
            'small_object_recall': groups,
            'ground_truth_size_pixels': {'width':describe([s[0] for s in sizes_all]), 'height':describe([s[1] for s in sizes_all])},
            'localization_matched_iou': describe(ious),
            'localization_best_iou_per_gt': describe(best_ious),
            'localization_scope': 'Matched IoU: TP only, biased toward detected objects. Best IoU: every GT, zero if no prediction, no one-to-one constraint; not another recall metric.',
            'matching': 'Confidence-descending greedy, highest-IoU unmatched GT; duplicate prediction is FP.',
            'undefined_precision_or_empty_group_recall': 'null, not zero',
            'thresholds_selected_on_wisard': False}
