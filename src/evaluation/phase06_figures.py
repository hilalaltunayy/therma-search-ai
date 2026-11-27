"""200 DPI source-validation diagnosis and descriptive cross-dataset figures."""
from pathlib import Path

from .person_detection import save_comparison


def plot_phase06(records, image_rows, object_rows, output, data_root):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    selections=[]
    groups={
        'missing_detection':[r for r in records if any(e['category']=='zero_overlap' for e in r['fn_errors'])],
        'poor_localization':[r for r in records if any(e['category']=='0_3_to_0_5' for e in r['fn_errors']+r['fp_errors'])],
        'duplicate_candidate':[r for r in records if any(e['duplicate_candidate'] for e in r['fp_errors'])],
        'small_object':[r for r in records if any(b[2]-b[0]<16 or b[3]-b[1]<16 for b in r['ground_truth_xyxy'])]}
    for category,rows in groups.items():
        for i,row in enumerate(rows[:2],1):
            name=f'{category}_{i:02d}.png'
            save_comparison(Path(data_root)/row['image_path'],row['ground_truth_xyxy'],row['detections'],row['matching'],output/name)
            selections.append({'figure':name,'member':row['member'],'selection':'first eligible source-validation order','category':category})
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    try:
        tp=[r['detections'][m['prediction_index']]['confidence'] for r in records for m in r['matching']['matches']]
        fp=[r['detections'][i]['confidence'] for r in records for i in r['matching']['fp_prediction_indices']]
        if tp or fp:
            axes[0].hist([tp,fp],bins=[.25+i*.05 for i in range(16)],label=['TP','FP'])
            axes[0].legend()
        else: axes[0].text(.1,.5,'No predictions at conf >= .25',transform=axes[0].transAxes)
        axes[0].set(title='Source val confidence (fixed >=.25)',xlabel='Confidence',ylabel='Predictions')
        native=[e['native_best_score'] for r in records for e in r['fn_errors'] if e.get('native_low_conf_overlap_candidate')]
        if native: axes[1].hist(native,bins=20)
        else: axes[1].text(.1,.5,'No low-conf overlap candidates',transform=axes[1].transAxes)
        axes[1].set(title='Native candidates near fixed FN (NOT recovered TP)',xlabel='Candidate score, IoU >= .50',ylabel='Unmatched GT (not unique predictions)')
        for ax in axes: ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        fig.tight_layout();fig.savefig(output/'confidence_diagnostics.png',dpi=200)
    finally: plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(16,4.8))
    try:
        for dataset,color in [('HIT-UAV validation','#0072B2'),('WiSARD IR descriptive','#D55E00')]:
            images=[r for r in image_rows if r['dataset']==dataset]
            objects=[r for r in object_rows if r['dataset']==dataset]
            if images:
                axes[0].hist([r['mean_8bit'] for r in images],bins=list(range(0,257,4)),weights=[1/len(images)]*len(images),histtype='step',label=dataset,color=color)
                axes[1].hist([r['std_8bit'] for r in images],bins=list(range(0,129,2)),weights=[1/len(images)]*len(images),histtype='step',label=dataset,color=color)
            if objects: axes[2].scatter([r['width_px'] for r in objects],[r['height_px'] for r in objects],s=5,alpha=.3,label=dataset,color=color)
        axes[0].set(title='Full-image display intensity',xlabel='8-bit luminance mean',ylabel='Fraction of cohort images')
        axes[1].set(title='Display-domain image contrast',xlabel='Luminance standard deviation',ylabel='Fraction of cohort images')
        axes[2].set(title='Ground-truth pixel sizes',xlabel='Width (original pixels)',ylabel='Height (original pixels)')
        for ax in axes:
            if ax.has_data(): ax.legend(fontsize=8)
        fig.suptitle('Descriptive cohorts; no radiometric calibration or causal domain-shift claim',fontsize=11)
        fig.tight_layout(rect=(0,0,1,.94));fig.savefig(output/'descriptive_domain_comparison.png',dpi=200)
    finally: plt.close(fig)
    return selections
