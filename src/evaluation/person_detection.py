"""Tek sınıf Person için sabit eşikte tanılama; mAP Ultralytics ile ayrı ölçülür."""
from pathlib import Path


def box_iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2-x1)*max(0, y2-y1)
    area_a, area_b = (a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])
    union = area_a+area_b-intersection
    return intersection/union if union > 0 else 0.0


def match_person_predictions(targets, detections, *, confidence=.25, iou_threshold=.5):
    """Confidence azalan sırada, her tahmine en yüksek IoU’lu boş GT; bire bir.

    Eşikler testten önce sabittir. Duplicate detection FP olur; TN nesne
    tespitinde tanımlanmaz. Bu özel tanılama resmi COCO mAP eşleyicisi değildir.
    """
    if not 0 <= confidence <= 1 or not 0 < iou_threshold <= 1:
        raise ValueError('Confidence/IoU eşiği geçersiz.')
    candidates = sorted((i for i, d in enumerate(detections) if d['confidence'] >= confidence),
                        key=lambda i: (-detections[i]['confidence'], i))
    remaining, matches, false_positive = set(range(len(targets))), [], []
    for index in candidates:
        best = max(remaining, key=lambda j: (box_iou(targets[j], detections[index]['bbox_xyxy']), -j), default=None)
        overlap = box_iou(targets[best], detections[index]['bbox_xyxy']) if best is not None else 0
        if best is not None and overlap >= iou_threshold:
            remaining.remove(best)
            matches.append({'prediction_index': index, 'target_index': best, 'iou': overlap})
        else:
            false_positive.append(index)
    return {'tp': len(matches), 'fp': len(false_positive), 'fn': len(remaining),
            'matches': matches, 'fp_prediction_indices': false_positive, 'fn_target_indices': sorted(remaining)}


def save_comparison(image_path, targets, detections, diagnostic, output_path):
    """Sol kırmızı GT; sağ mavi tahmin/FP mor; kaçırılan GT sağ turuncu kesik."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from PIL import Image
    with Image.open(image_path) as image:
        image.load()
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for ax in axes:
            ax.imshow(image, cmap='gray' if image.mode == 'L' else None)
            ax.axis('off')
    try:
        def rectangle(ax, box, color, text, dashed=False):
            x1, y1, x2, y2 = box
            ax.add_patch(Rectangle((x1, y1), x2-x1, y2-y1, fill=False, edgecolor=color,
                                   linewidth=1.3, linestyle='--' if dashed else '-'))
            ax.text(x1, y1, text, color=color, fontsize=7)
        for box in targets:
            rectangle(axes[0], box, 'red', 'GT Person')
        for i, detection in enumerate(detections):
            fp = i in diagnostic['fp_prediction_indices']
            rectangle(axes[1], detection['bbox_xyxy'], 'magenta' if fp else 'deepskyblue',
                      f"{'FP' if fp else 'Person'} {detection['confidence']:.2f}")
        for index in diagnostic['fn_target_indices']:
            rectangle(axes[1], targets[index], 'orange', 'FN ground truth', dashed=True)
        axes[0].set_title('Ground truth (red) — annotated Person', fontsize=10)
        axes[1].set_title('Predictions (blue), FP (magenta)\nMissed GT / FN (orange dashed)', fontsize=10)
        fig.suptitle(f"{Path(image_path).name} | TP={diagnostic['tp']} FP={diagnostic['fp']} FN={diagnostic['fn']} | exploratory baseline", fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, .90))
        fig.savefig(output_path, dpi=200)
    finally:
        plt.close(fig)
