"""Source-validation diagnostics; categories are descriptive, not causes or threshold recommendations."""
from collections import Counter
import json
import math
from pathlib import Path

from PIL import Image

from .person_detection import box_iou, match_person_predictions
from .wisard_external_metrics import small_object_recall

IOU_GROUPS = ('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5')


def iou_group(value):
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Invalid IoU.')
    return ('zero_overlap' if value == 0 else 'gt_0_lt_0_1' if value < .1 else
            '0_1_to_0_3' if value < .3 else '0_3_to_0_5' if value < .5 else 'ge_0_5')


def diagnose_image(targets, predictions, native_predictions=None):
    """Fixed conf=.25 / IoU=.50; native candidates are NOT rematched/recoverable TP."""
    if any(p['confidence'] < .25 for p in predictions):
        raise ValueError('Fixed diagnostic predictions must satisfy confidence >= .25.')
    match=match_person_predictions(targets,predictions,confidence=.25,iou_threshold=.5)
    matched_gt={r['target_index'] for r in match['matches']}
    fn_rows,fp_rows=[],[]
    for i in match['fn_target_indices']:
        best=max((box_iou(targets[i],p['bbox_xyxy']) for p in predictions),default=0)
        row={'gt_index':i,'max_fixed_iou':best,'category':iou_group(best),
             'fixed_image_prediction_count':len(predictions)}
        if native_predictions is not None:
            candidate=max(native_predictions,key=lambda p:(box_iou(targets[i],p['bbox_xyxy']),p['confidence']),default=None)
            overlap=box_iou(targets[i],candidate['bbox_xyxy']) if candidate else 0
            score=candidate['confidence'] if candidate else None
            row.update(native_best_iou=overlap,native_best_score=score,
                       native_low_conf_overlap_candidate=bool(candidate and overlap>=.5 and .001<=score<.25),
                       native_high_conf_discrepancy_candidate=bool(candidate and overlap>=.5 and score>=.25))
        fn_rows.append(row)
    for i in match['fp_prediction_indices']:
        best_index=max(range(len(targets)),key=lambda j:box_iou(targets[j],predictions[i]['bbox_xyxy']),default=None)
        overlap=box_iou(targets[best_index],predictions[i]['bbox_xyxy']) if best_index is not None else 0
        fp_rows.append({'prediction_index':i,'max_gt_iou':overlap,'best_gt_index':best_index,
                        'category':iou_group(overlap),
                        'duplicate_candidate':overlap>=.5 and best_index in matched_gt})
    return {'matching':match,'fn_errors':fn_rows,'fp_errors':fp_rows,
            'small_object_recall':small_object_recall(targets,matched_gt)}


def load_native_predictions(path, image_rows):
    """Pinned Ultralytics JSON: image stem ID, category 0, rounded pixel xywh.

    IDs are mapped explicitly; unknown IDs are errors. An empty list is a valid
    no-predictions export. Rounding-sized boundary drift is retained, not repaired.
    """
    keys={}
    for row in image_rows:
        stem=Path(row['image_path']).stem
        key=int(stem) if stem.isnumeric() else stem
        if str(key) in keys:
            raise ValueError('Ambiguous native image ID.')
        keys[str(key)]=row['member']
    result={r['member']:[] for r in image_rows}
    values=json.loads(Path(path).read_text())
    if not isinstance(values,list):
        raise ValueError('Native predictions export must be a list.')
    for entry in values:
        key=str(entry['image_id'])
        if key not in keys or entry['category_id'] != 0:
            raise ValueError('Unknown native image/category ID; no heuristic ID or class mapping.')
        x,y,w,h=map(float,entry['bbox'])
        confidence=float(entry['score'])
        if not all(math.isfinite(v) for v in (x,y,w,h,confidence)) or min(w,h)<0 or not .001<=confidence<=1:
            raise ValueError('Invalid native box/score.')
        row=next(r for r in image_rows if r['member']==keys[key])
        if x < -.002 or y < -.002 or x+w > row['width']+.002 or y+h > row['height']+.002:
            raise ValueError('Native box exceeds rounding tolerance at original image boundaries.')
        result[keys[key]].append({'bbox_xyxy':[x,y,x+w,y+h],'confidence':confidence,
                                  'class_id':0,'class_name':'Person','degenerate_after_JSON_rounding':min(w,h)==0})
    return result


def summarize_histogram(hist):
    n=sum(hist)
    if not n: raise ValueError('Empty pixel sample.')
    average=sum(i*count for i,count in enumerate(hist))/n
    variance=sum(count*(i-average)**2 for i,count in enumerate(hist))/n
    def quantile(fraction):
        cumulative=0
        for value,count in enumerate(hist):
            cumulative+=count
            if cumulative>=max(1,math.ceil(n*fraction)): return value
    lo,hi=quantile(.05),quantile(.95)
    return {'pixel_count':n,'mean_8bit':average,'std_8bit':math.sqrt(variance),
            'p05_8bit':lo,'p50_8bit':quantile(.5),'p95_8bit':hi,'p95_minus_p05':hi-lo,
            'fraction_0':hist[0]/n,'fraction_255':hist[255]/n}


def image_descriptors(path, targets):
    """Display-domain 8-bit luminance, not radiometric temperature or causal contrast."""
    with Image.open(path) as image:
        image.load()
        mode=image.mode
        gray=image.convert('L')
    try:
        hist=gray.histogram()
        whole=summarize_histogram(hist)
        whole.update(source_mode=mode,grayscale_conversion='Pillow convert(L); display luminance, not temperature')
        objects=[]
        for i,(x1,y1,x2,y2) in enumerate(targets):
            inner=(max(0,math.floor(x1)),max(0,math.floor(y1)),min(gray.width,math.ceil(x2)),min(gray.height,math.ceil(y2)))
            pad=max(4,math.ceil(max(x2-x1,y2-y1)/2))
            outer=(max(0,inner[0]-pad),max(0,inner[1]-pad),min(gray.width,inner[2]+pad),min(gray.height,inner[3]+pad))
            with gray.crop(inner) as crop: h1=crop.histogram()
            with gray.crop(outer) as crop: h2=crop.histogram()
            ring=[a-b for a,b in zip(h2,h1)]
            inside=summarize_histogram(h1)
            surroundings=summarize_histogram(ring) if sum(ring)>0 else None
            objects.append({'gt_index':i,'width_px':x2-x1,'height_px':y2-y1,
                'roi_mean_8bit':inside['mean_8bit'],'roi_std_8bit':inside['std_8bit'],
                'ring_mean_8bit':surroundings['mean_8bit'] if surroundings else None,
                'signed_roi_ring_difference':inside['mean_8bit']-surroundings['mean_8bit'] if surroundings else None,
                'absolute_roi_ring_difference':abs(inside['mean_8bit']-surroundings['mean_8bit']) if surroundings else None})
        return whole,objects,hist
    finally:
        gray.close()


def aggregate_diagnoses(records):
    if not records: raise ValueError('No source-validation records.')
    counts={k:sum(r['matching'][k] for r in records) for k in ('tp','fp','fn')}
    tp,fp,fn=counts['tp'],counts['fp'],counts['fn']
    fn_groups=Counter(e['category'] for r in records for e in r['fn_errors'])
    fp_groups=Counter(e['category'] for r in records for e in r['fp_errors'])
    return {**counts,'images':len(records),'gt':tp+fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'fp_per_image':fp/len(records),
            'fn_by_max_fixed_iou':{k:fn_groups[k] for k in IOU_GROUPS},
            'fp_by_max_gt_iou':{k:fp_groups[k] for k in IOU_GROUPS},
            'duplicate_prediction_candidates':sum(e['duplicate_candidate'] for r in records for e in r['fp_errors']),
            'images_without_fixed_predictions':sum(not r['detections'] for r in records),
            'native_low_conf_FN_overlap_candidates':sum(e.get('native_low_conf_overlap_candidate',False) for r in records for e in r['fn_errors']),
            'native_high_conf_FN_discrepancy_candidates':sum(e.get('native_high_conf_discrepancy_candidate',False) for r in records for e in r['fn_errors']),
            'native_candidates_warning':'Not one-to-one matched; candidates can be shared by GTs. NOT recovered/recoverable TP or a threshold recommendation.'}
