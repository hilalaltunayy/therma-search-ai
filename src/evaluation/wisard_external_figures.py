"""Gerçek değerlendirme kayıtlarından 200 DPI şekiller; boş kategoride bulgu uydurmaz."""
import math
import textwrap
from pathlib import Path

from PIL import Image

from .person_detection import save_comparison
from .wisard_external_metrics import small_object_recall


def review_contact_sheets(manifest, data_root, output):
    import matplotlib.pyplot as plt
    rows = [r for r in manifest['images'] if r['reason'] == 'empty_annotation_pending_review']
    for start in range(0, len(rows), 6):
        page = rows[start:start+6]
        columns = min(3,len(page))
        nrows = math.ceil(len(page)/columns)
        fig, axes = plt.subplots(nrows, columns, figsize=(4.7*columns,4*nrows), squeeze=False)
        try:
            for axis in axes.flat:
                axis.set_axis_off()
            for axis, row in zip(axes.flat, rows[start:start+6]):
                with Image.open(Path(data_root)/row['image_path']) as image:
                    axis.imshow(image, cmap='gray' if image.mode == 'L' else None)
                axis.set_title(f"IR {row['frame']:08d} | empty TXT\n{textwrap.fill(Path(row['member']).name, 48)}", fontsize=8)
            fig.suptitle('Excluded, uncertain empty annotations — human presence NOT adjudicated', fontsize=11)
            fig.tight_layout(rect=(0,0,1,.94))
            fig.savefig(output/f'empty_annotation_review_{start//6+1:02d}.png', dpi=200)
        finally:
            plt.close(fig)


def save_fixed_figures(records, metrics, data_root, output):
    import matplotlib.pyplot as plt
    categories = {
        'comparison': records,
        'true_positive': [r for r in records if r['matching']['tp']],
        'false_positive': [r for r in records if r['matching']['fp']],
        'false_negative': [r for r in records if r['matching']['fn']],
        'small_person': [r for r in records if small_object_recall(r['ground_truth_xyxy'], [], sizes=r['ground_truth_sizes_px'])['width_lt_16']['ground_truth_count']
                         or small_object_recall(r['ground_truth_xyxy'], [], sizes=r['ground_truth_sizes_px'])['height_lt_16']['ground_truth_count']],
    }
    selections = []
    for category, selected in categories.items():
        # Tüm zaman aralığına yayılmış deterministik örnekler; performans seçimi değildir.
        n = min(4, len(selected))
        for i, index in enumerate(sorted({round(j*(len(selected)-1)/max(1,n-1)) for j in range(n)}), 1):
            row = selected[index]
            filename = f'{category}_{i:02d}.png'
            if category == 'small_person':
                save_small_detail(row,data_root,output/filename)
            else:
                save_comparison(Path(data_root)/row['image_path'], row['ground_truth_xyxy'], row['detections'], row['matching'], output/filename)
            selections.append({'file': filename, 'category': category, 'member': row['member']})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    try:
        tp_conf = [r['detections'][m['prediction_index']]['confidence'] for r in records for m in r['matching']['matches']]
        fp_conf = [r['detections'][i]['confidence'] for r in records for i in r['matching']['fp_prediction_indices']]
        if tp_conf or fp_conf:
            axes[0].hist([tp_conf, fp_conf], bins=[.25+i*.05 for i in range(16)], label=['TP', 'FP'], color=['#0072B2','#CC79A7'])
            axes[0].legend()
        else:
            axes[0].text(.5,.5,'No predictions at confidence >= 0.25',transform=axes[0].transAxes,ha='center')
        axes[0].set(title='Fixed-threshold confidence distributions', xlabel='Confidence (truncated at 0.25)', ylabel='Predictions')
        ious = [m['iou'] for r in records for m in r['matching']['matches']]
        if ious:
            axes[1].hist(ious, bins=[.5+i*.05 for i in range(11)])
        else:
            axes[1].text(.5,.5,'No true positives',transform=axes[1].transAxes,ha='center')
        axes[1].set(title='Localization: matched TP only', xlabel='Matched IoU (>=0.50)', ylabel='True positives')
        fig.tight_layout()
        fig.savefig(output/'confidence_and_localization.png', dpi=200)
    finally:
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    try:
        totals = [metrics[k] for k in ('tp','fp','fn')]
        axes[0].bar(['TP','FP','FN'],totals,color=['#0072B2','#CC79A7','#E69F00'])
        axes[0].set(title=f"Fixed threshold | n={metrics['evaluated_images']} images", ylabel='Objects / detections')
        for i, n in enumerate(totals):
            axes[0].text(i,n,str(n),ha='center',va='bottom')
        groups = list(metrics['small_object_recall'].values())
        axes[1].bar(range(3), [r['recall'] if r['recall'] is not None else 0 for r in groups])
        axes[1].set_xticks(range(3),['width<16 px','height<16 px','both<16 px'])
        axes[1].set(ylim=(0,1.18),title='Small-person recall with explicit GT denominators',ylabel='Recall')
        for i, r in enumerate(groups):
            text = f"{r['detected_count']}/{r['ground_truth_count']}" if r['ground_truth_count'] else 'N/A (0 GT)'
            axes[1].text(i, r['recall'] or 0, text, ha='center',va='bottom')
        fig.tight_layout()
        fig.savefig(output/'fixed_metrics_and_small_recall.png',dpi=200)
    finally:
        plt.close(fig)
    fig, axis = plt.subplots(figsize=(6,5))
    try:
        tp, fp, fn = totals
        axis.imshow([[tp,fp],[fn,0]],cmap='Blues')
        for x,y,text in [(0,0,str(tp)),(1,0,str(fp)),(0,1,str(fn)),(1,1,'N/A')]:
            axis.text(x,y,text,ha='center',va='center',color='red')
        axis.set_xticks([0,1],['Person','Background'])
        axis.set_yticks([0,1],['Person','Background'])
        axis.set(title='Fixed-threshold confusion | conf=.25, IoU=.50',xlabel='Ground truth',ylabel='Prediction')
        fig.tight_layout()
        fig.savefig(output/'fixed_confusion_matrix.png',dpi=200)
    finally:
        plt.close(fig)
    return selections



def save_small_detail(row, data_root, output_path):
    """Zoom around a small GT in original pixel coordinates; global matching is unchanged."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    sizes=row['ground_truth_sizes_px']
    eligible=[i for i,(w,h) in enumerate(sizes) if w<16 or h<16]
    index=min(eligible,key=lambda i:sizes[i][0]*sizes[i][1])
    target=row['ground_truth_xyxy'][index]
    x1,y1,x2,y2=target
    pad=max(32,x2-x1,y2-y1)
    fig,axes=plt.subplots(1,2,figsize=(10,5))
    try:
        with Image.open(Path(data_root)/row['image_path']) as image:
            for ax in axes:
                ax.imshow(image,cmap='gray' if image.mode=='L' else None)
                ax.set_xlim(max(0,x1-pad),min(image.width,x2+pad))
                ax.set_ylim(min(image.height,y2+pad),max(0,y1-pad))
                ax.axis('off')
        for gt in row['ground_truth_xyxy']:
            a,b,c,d=gt
            axes[0].add_patch(Rectangle((a,b),c-a,d-b,fill=False,edgecolor='red',linewidth=1.5))
        for i,pred in enumerate(row['detections']):
            a,b,c,d=pred['bbox_xyxy']
            fp=i in row['matching']['fp_prediction_indices']
            color='magenta' if fp else 'deepskyblue'
            axes[1].add_patch(Rectangle((a,b),c-a,d-b,fill=False,edgecolor=color,linewidth=1.5))
        missed=index in row['matching']['fn_target_indices']
        if missed:
            axes[1].add_patch(Rectangle((x1,y1),x2-x1,y2-y1,fill=False,edgecolor='orange',linestyle='--',linewidth=2))
        axes[0].set_title('Ground truth (red) | contextual crop',fontsize=10)
        axes[1].set_title('TP blue / FP magenta / selected FN orange',fontsize=10)
        fig.suptitle(f"IR {row['frame']:08d} | selected GT {sizes[index][0]:.2f} x {sizes[index][1]:.2f} px | {'missed' if missed else 'detected'} at fixed threshold",fontsize=11)
        fig.tight_layout(rect=(0,0,1,.92))
        fig.savefig(output_path,dpi=200)
    finally:
        plt.close(fig)


def save_map_curves(metric_result, output):
    """Native mAP eğri verisi -> 200 DPI PNG; optimum confidence seçilmez."""
    import matplotlib.pyplot as plt
    try:
        curves = metric_result.curves_results
    except AttributeError:
        curves = []
    payload = []
    for index, item in enumerate(curves):
        x, y, xlabel, ylabel = item
        x = x.tolist() if hasattr(x,'tolist') else list(x)
        y = y.tolist() if hasattr(y,'tolist') else list(y)
        series = y if y and isinstance(y[0], list) else [y]
        if not x or not series or any(len(values) != len(x) for values in series):
            continue
        if not all(math.isfinite(float(v)) for values in [x,*series] for v in values):
            raise ValueError('Ultralytics eğri verisi sonlu değil.')
        fig, ax = plt.subplots(figsize=(7,5))
        try:
            for values in series:
                ax.plot(x, values)
            ax.set(xlabel=xlabel, ylabel=ylabel, xlim=(0,1),ylim=(0,1),title=f'Person: Ultralytics {ylabel} vs {xlabel}')
            ax.grid(alpha=.2)
            fig.tight_layout()
            filename=f'map_curve_{index:02d}_{ylabel}_vs_{xlabel}.png'
            fig.savefig(output/filename,dpi=200)
            payload.append({'file':filename,'x':x,'y':series,'xlabel':xlabel,'ylabel':ylabel})
        finally:
            plt.close(fig)
    return {'curves':payload,'available':bool(payload),
            'note':'Ultralytics metric curves at mAP confidence floor .001; no threshold selection. Empty if unavailable (e.g., no predictions).'}
