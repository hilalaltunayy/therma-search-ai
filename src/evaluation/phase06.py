"""Phase 06: frozen HIT-UAV checkpoint diagnostics on original filtered validation only.

WiSARD is descriptive/already inspected; its scores never select experiments.
No train call, checkpoint/dataset download, source split change or test inference.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import time
import uuid

from src.data.audit import file_digest
from src.data.wisard_sample import describe
from src.evaluation.inference import load_person_detector, predict_person
from src.evaluation.wisard_external import environment_metadata, evaluation_device
from src.evaluation.wisard_external_data import prepare_ir_evaluation
from src.evaluation.wisard_external_metrics import aggregate_fixed_records
from src.data.wisard_reports import _csv, _json
from src.training.hit_uav_yolo import POLICY, prepare_hit_uav_yolo, validate_prepared_dataset
from .error_analysis import diagnose_image, image_descriptors, load_native_predictions, aggregate_diagnoses
from .phase06_evidence import REPORTED_WISARD
from .phase06_figures import plot_phase06


def protocol_review():
    return {
        'fixed':{'confidence':.25,'matching_iou':.5,'nms_iou':.7,'max_det':300,'imgsz':640,
                 'assignment':'confidence descending, highest-IoU unmatched GT; one-to-one'},
        'native':{'confidence_floor':.001,'imgsz':640,'nms_iou':.7,'max_det':300,
                  'map_iou_grid':[.5+i*.05 for i in range(10)],
                  'assignment':'native IoU-based unique matching, per IoU threshold; not custom confidence-greedy assignment',
                  'precision_recall':'native curve optimum is not fixed-threshold P/R'},
        'preprocessing_audit':[
            'Native val uses rectangular dataset batches and dataset pad=.5 in Ultralytics 8.3.228; single-image predict can use minimum-stride rectangular padding.',
            'Same imgsz=640 does not guarantee identical inference tensor shape. Native batch_shapes and predictor args are recorded when available.',
            'FP32 is explicit in native validation; predictor effective half/rect/device are inspected rather than inferred from CPU/GPU alone.',
            'Native JSON is original-pixel xywh rounded to 3 decimals, score to 5; fixed JSONL is original-pixel xyxy. Rounding can affect IoU boundary comparisons.',
            'NMS, batch shape, inference preprocessing, score-floor candidate competition and distinct assignment procedures can cause differences; a discrepancy alone is not proof of a bug.'],
        'noncausal_interpretation':'Candidate overlap in a separate native pass is not one-to-one matched and is not recovered TP. No threshold selection is performed.'}


def _native_callback(audit):
    def capture(validator):
        dataset=validator.dataloader.dataset
        shapes=getattr(dataset,'batch_shapes',None)
        audit['native_batch_shapes']=shapes.tolist() if hasattr(shapes,'tolist') else shapes
        audit['native_effective_args']={k:getattr(validator.args,k,None) for k in ('imgsz','rect','batch','half','device','conf','iou','max_det','workers','augment')}
        audit['native_seen_images']=getattr(validator,'seen',None)
        audit['native_json_prediction_count']=len(validator.jdict)
    return capture


def _describe_dataset(root, rows, dataset):
    images,objects=[],[]
    for row in rows:
        targets=row['ground_truth_xyxy']
        whole,rois,hist=image_descriptors(Path(root)/row['image_path'],targets)
        images.append({'dataset':dataset,'member':row['member'],**whole})
        objects.extend({'dataset':dataset,'member':row['member'],**r} for r in rois)
    return images,objects


def _baseline_membership(checkpoint, manifest):
    path=checkpoint.parent/'dataset_manifest.json'
    if not path.is_file():
        return {'status':'historical_manifest_unavailable','note':'Policy reused; membership against the actual previous training run not independently verified.'}
    old=json.loads(path.read_text())
    if old.get('status')!='ready': raise ValueError('Historical training data manifest is not ready.')
    if old.get('policy')!=POLICY: raise ValueError('Historical training manifest filtering policy differs.')
    def membership(rows):
        return {(r['source_filename'],r['image_sha256']) for r in rows if r['split']=='val' and r['disposition']=='included'}
    if membership(old['images'])!=membership(manifest['images']):
        raise ValueError('Reconstructed validation membership differs from the previous training manifest.')
    return {'status':'val_membership_and_image_hashes_match','manifest_sha256':file_digest(path)}


def _write_report(output,summary,records,image_rows,object_rows):
    text=['# Faz 06 — Kaynak validation hata analizi',
          f"Durum: {summary['status']} · UTC: {summary['started_utc']} · Git: `{summary['git_commit']}`",
          '## Kanıt sınırları',
          'Yeni model çıkarımı yalnızca özgün HIT-UAV validation üyelerinin önceki politika ile filtrelenmiş kopyasında yapılır. '
          'Bu validation, baseline checkpoint seçimi/erken durdurmada zaten kullanılmıştır; bağımsız tarafsız final test değildir. '
          'Eğitim yapılmaz; HIT-UAV test görüntüleri okunmaz/çıkarıma verilmez. Tam ZIP hash’i dosya kimliğidir.',
          f"Girdi hash’leri: {summary['hashes']}. Eğitim manifesti karşılaştırması: {summary.get('baseline_membership')}.",
          f"Pakette bildirilen model hash’iyle yeni checkpoint kimliği eşleşiyor: {summary.get('reported_wisard_model_identity_matches')}. Eşleşmiyorsa eski dış sonuçlar bu modele bağlanmaz.",
          f"WiSARD bağlamı (kullanıcı sonucu ve önceden incelenmiş paket, yeni skor değil): {REPORTED_WISARD}.",
          'Ek paket üç özet dosyası içerir; CSV/JSON aritmetiği incelenmiştir, ham kutular ve native export pakette yoktur. '
          '591 sıfır örtüşme FN, ilgili GT ile örtüşen fixed tahmin bulunmamasıdır; tüm görüntüde tahmin yok demek değildir. '
          '410 düşük güvenli native aday birden fazla GT tarafından paylaşılabilir, kurtarılabilir TP veya eşik önerisi değildir.',
          '## Yeni gözlenen kaynak-validation ölçümleri']
    if summary['status']=='complete':
        text += [f"Sabit eşik sonuçları: {summary['source_validation_diagnosis']}.",
                 f"Native validation mAP: {summary['source_native_map']}. Özel küçük nesne recall ve IoU özetleri: {summary['source_fixed_metrics']}.",
                 f"Kaynak filtreleme: {summary['source_coverage']}. Aynı DontCare/sıfır ham anotasyon dışlama politikası korunur. "
                 'Diğer-sınıf-only arka plan görüntüleri önceki politika gereğince dahildir; bunların Person etiket tamlığı varsayımı sürer.',
                 '## Betimsel boyut/yoğunluk/kontrast karşılaştırması',
                 f"WiSARD betimsel durum: {summary['wisard_descriptive_status']}. Kayıtlar display-domain L kanalındadır; termal sıcaklık değildir. "
                 'GT ROI ile çevre halkası farkları, tam görüntü ortalama/std ve P95−P05 kaydedilir. Farklı sahne ve anotasyon filtreleri karıştırıcıdır; nedensellik kurulmaz.']
        text += ['### Küçük nesne recall paydaları', '| GT grubu | Tespit | Toplam GT | Recall |', '|---|---:|---:|---:|']
        for group,stats in summary['source_fixed_metrics']['small_object_recall'].items():
            text.append(f"| {group} | {stats['detected_count']} | {stats['ground_truth_count']} | {stats['recall']} |")
        for dataset in sorted({r['dataset'] for r in image_rows}):
            ims=[r for r in image_rows if r['dataset']==dataset]
            obs=[r for r in object_rows if r['dataset']==dataset]
            text += [f"{dataset}: görüntü={len(ims)}, GT={len(obs)}, genişlik={describe([r['width_px'] for r in obs])}, "
                     f"yükseklik={describe([r['height_px'] for r in obs])}, görüntü ortalama yoğunluğu={describe([r['mean_8bit'] for r in ims])}, "
                     f"görüntü std={describe([r['std_8bit'] for r in ims])}."]
    else: text += [f"Analiz tamamlanmadı: {summary.get('error')}. Kısmi dosyalar başarılı deney sonucu değildir."]
    text += ['## Olası açıklamalar (kanıtlanmış nedenler değildir)',
             'Fixed sıfır örtüşme; düşük skor, hiç öneri üretilmemesi, arka plan karışması veya büyük konum hatasıyla uyumludur. '
             'Yakın ama IoU<.50 kutular lokalizasyon/etiket geometrisi sorunuyla uyumludur. Küçük hedeflerin birkaç piksel kayması IoU’yu düşürebilir. '
             'Düşük güvenli native örtüşmeler skor dağılımı araştırmasını destekler; kalibrasyon bozukluğunu veya eşik düşürmenin net kazancını kanıtlamaz. '
             'Yoğunluk/kontrast ve kamera sahne farkları olası açıklamalardır; display luminance karşılaştırması radyometrik domain ölçümü değildir.',
             '## Çözülmemiş hipotezler ve yöntem tutarlılığı',
             'Native ve fixed farklı skor tabanları, eşleme ve padding/batch yolları kullanır. Kare 245 için paket bir yüksek güvenli native uyuşmazlık adayı bildirir; '
             'bu geliştirme ortamında ham tahminler olmadan neden veya bug doğrulanmamıştır. CPU kullanımı tek başına düşük performans açıklaması değildir. '
             'Etiket eksikliği, skor kalibrasyonu, NMS etkisi, padding/resize farkları ve gerçek sahne karışması kontrollü kaynak-val incelemesi ister.',
             f"Protokol incelemesi: {summary['protocol_review']}. Runtime gözlemleri protocol_runtime.json içindedir.",
             '## Faz 07 kontrollü deney sınırı',
             'Adaylar yalnızca HIT-UAV train/val üzerinde sınanır; plan experiment_matrix.json ve phase07_experiment_matrix.md içindedir. '
             'WiSARD artık incelenmiş tanılama veri setidir, pristine final holdout değildir. WiSARD skorları confidence, hiperparametre veya checkpoint seçemez. '
             'Birincil seçim filtered HIT-UAV val mAP50:95, yardımcı küçük nesne recall/FP-görüntü/hesap maliyeti üzerinden önceden tanımlanır; val sızıntı riski korunur. '
             'Final genelleme için farklı uçuş/saha/görevlerden, model seçimine kapalı bağımsız dış veri ve doğrulanmış negatif sahneler gerekir.',
             '## Tekrarlanabilirlik',f"Ortam: {summary['environment']}; cihaz: {summary.get('runtime')}; süre: {summary.get('seconds')} saniye. "
             'Kaynak dosyalar ve checkpoint değiştirilmez; her run yeni klasördedir. Örnekler görsel inceleme içindir, temsilî istatistik örneklemi değildir.']
    for path in sorted((output/'figures').glob('*.png')):
        text.append(f'![{path.stem}](figures/{path.name})')
    (output/'error_analysis_report.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')


def run_phase06(checkpoint, hit_uav_zip, output_root, work_root, *, git_commit, wisard_zip=None, project_root=None):
    checkpoint,hit_uav_zip=Path(checkpoint).resolve(),Path(hit_uav_zip).resolve()
    output=Path(output_root).resolve()/(datetime.now(timezone.utc).strftime('run_phase06_%Y%m%dT%H%M%SZ_')+uuid.uuid4().hex[:8])
    output.mkdir(parents=True,exist_ok=False);(output/'figures').mkdir()
    data_root=Path(work_root).resolve()/output.name/'source_val'
    print('Phase 06 output:',output)
    summary={'status':'initializing','started_utc':datetime.now(timezone.utc).isoformat(),'git_commit':git_commit,
             'environment':environment_metadata(),'protocol_review':protocol_review(),'hashes':{},
             'source_validation_diagnosis':None,'source_native_map':None,'source_fixed_metrics':None,
             'wisard_reference_not_new_evaluation':REPORTED_WISARD,'wisard_descriptive_status':'not_run',
             'analysis_scope':'filtered_original_HIT_UAV_validation_only','training_executed':False,'test_inference_executed':False,'wisard_used_for_selection':False}
    records,image_rows,object_rows=[],[],[]
    protocol={};manifest=None;started=time.monotonic()
    try:
        for name,path in [('checkpoint',checkpoint),('hit_uav_zip',hit_uav_zip)]:
            if not path.is_file(): raise FileNotFoundError(f'Missing {name}; no download: {path}')
            summary['hashes'][name]={'path':str(path),'sha256':file_digest(path)}
        summary['reported_wisard_model_identity_matches']=(summary['hashes']['checkpoint']['sha256']==REPORTED_WISARD['package_reported_model_sha256'])
        try:
            _,manifest=prepare_hit_uav_yolo(hit_uav_zip,data_root,code_revision=git_commit,splits=('val',))
        finally:
            for file in ('dataset_manifest.json','image_dispositions.csv','data.yaml'):
                if (data_root/file).exists(): shutil.copy2(data_root/file,output/file)
        summary['source_coverage']=manifest['splits']['val']
        summary['baseline_membership']=_baseline_membership(checkpoint,manifest)
        if summary['environment']['packages']['ultralytics']!='8.3.228': raise RuntimeError('ultralytics==8.3.228 is required.')
        runtime=evaluation_device();summary['runtime']=runtime
        included=[{**r,'member':r['source_member'],'ground_truth_xyxy':r['person_xyxy_pixels']} for r in manifest['images'] if r['disposition']=='included']
        model=load_person_detector(checkpoint)
        model.add_callback('on_val_end',_native_callback(protocol))
        native=model.val(data=str(data_root/'data.yaml'),split='val',imgsz=640,conf=.001,iou=.7,max_det=300,
                         batch=runtime['batch'],device=runtime['device'],half=False,workers=0,cache=False,rect=True,plots=False,save_json=True,
                         project=str(output),name='native_val',exist_ok=False)
        positive_images=sum(bool(r['ground_truth_xyxy']) for r in included)
        if sum(map(int,native.nt_per_class))!=sum(len(r['ground_truth_xyxy']) for r in included) or sum(map(int,native.nt_per_image))!=positive_images:
            raise ValueError('Native GT/positive-image denominators disagree with source validation.')
        if protocol.get('native_seen_images') not in (None,len(included)): raise ValueError('Native skipped source validation images.')
        json_path=output/'native_val/predictions.json'
        if json_path.is_file(): native_by_image=load_native_predictions(json_path,included)
        elif protocol.get('native_json_prediction_count')==0: native_by_image={r['member']:[] for r in included}
        else: raise ValueError('Native JSON export missing, no confirmed empty export.')
        for row in included:
            prediction=predict_person(model,str(data_root/row['image_path']),confidence=.25,imgsz=640,device=runtime['device'])
            if prediction['image']!={'width':row['width'],'height':row['height']}: raise ValueError('Prediction image dimensions differ.')
            analysis=diagnose_image(row['ground_truth_xyxy'],prediction['detections'],native_by_image[row['member']])
            records.append({**row,**prediction,**analysis})
        predictor=getattr(model,'predictor',None)
        if predictor is not None:
            protocol['fixed_predictor_args']={k:getattr(predictor.args,k,None) for k in ('imgsz','rect','half','device','conf','iou','max_det','augment')}
            protocol['fixed_target_imgsz']=getattr(predictor,'imgsz',None)
        summary['source_validation_diagnosis']=aggregate_diagnoses(records)
        summary['source_fixed_metrics']=aggregate_fixed_records(records)
        maps={'mAP50':float(native.box.map50),'mAP50_95':float(native.box.map)}
        if not all(math.isfinite(v) and 0<=v<=1 for v in maps.values()): raise ValueError('Invalid native source-validation mAP.')
        summary['source_native_map']=maps
        image_rows,object_rows=_describe_dataset(data_root,included,'HIT-UAV validation')
        for row in object_rows:
            record=next(r for r in records if r['member']==row['member'])
            row['matched_gt']=row['gt_index'] in {m['target_index'] for m in record['matching']['matches']}
        if wisard_zip is not None and Path(wisard_zip).is_file():
            path=Path(wisard_zip).resolve()
            summary['hashes']['wisard_zip']={'path':str(path),'sha256':file_digest(path)}
            wr=Path(work_root).resolve()/output.name/'wisard_descriptive'
            wm=prepare_ir_evaluation(path,wr)
            _json(output/'wisard_descriptive_manifest.json',wm)
            if wm['status']=='ready':
                ws=[{**r,'ground_truth_xyxy':[b['xyxy'] for b in r['boxes']]} for r in wm['images'] if r['included']]
                wi,wo=_describe_dataset(wr,ws,'WiSARD IR descriptive');image_rows+=wi;object_rows+=wo
                summary['wisard_descriptive_status']='pixels_and_GT_only_no_inference_no_selection'
            else: summary['wisard_descriptive_status']='invalid_IR_manifest_no_pixel_comparison'
        else: summary['wisard_descriptive_status']='archive_unavailable_historical_reference_only'
        selections=plot_phase06(records,image_rows,object_rows,output/'figures',data_root)
        _json(output/'figure_manifest.json',selections)
        validate_prepared_dataset(data_root)
        summary['status']='complete'
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}',source_validation_diagnosis=None,source_native_map=None,source_fixed_metrics=None)
        raise
    finally:
        for name,r in summary['hashes'].items():
            r['sha256_after']=file_digest(Path(r['path'])) if Path(r['path']).is_file() else None
        summary['inputs_unchanged']=all(r['sha256']==r['sha256_after'] for r in summary['hashes'].values()) if summary['hashes'] else None
        if summary['inputs_unchanged'] is False: summary.update(status='failed',error='Input hash changed; results invalidated.',source_validation_diagnosis=None,source_native_map=None,source_fixed_metrics=None)
        summary['seconds']=time.monotonic()-started
        _json(output/'protocol_runtime.json',protocol)
        _json(output/'phase06_summary.json',summary)
        with (output/'source_val_predictions.jsonl').open('w',encoding='utf-8') as stream:
            for r in records: stream.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
        per_image=[{'member':r['member'],'gt':len(r['ground_truth_xyxy']),'predictions':len(r['detections']),
                    **{k:r['matching'][k] for k in ('tp','fp','fn')},
                    **{'fn_'+k:sum(e['category']==k for e in r['fn_errors']) for k in ('zero_overlap','gt_0_lt_0_1','0_1_to_0_3','0_3_to_0_5','ge_0_5')},
                    'duplicate_candidates':sum(e['duplicate_candidate'] for e in r['fp_errors'])} for r in records]
        for name,key in [('fn_errors.csv','fn_errors'),('fp_errors.csv','fp_errors')]:
            rows=[{'member':r['member'],**e} for r in records for e in r[key]]
            _csv(output/name,rows,sorted({k for r in rows for k in r}) if rows else ['member','category'])
        _csv(output/'per_image_errors.csv',per_image,list(per_image[0]) if per_image else ['member','tp','fp','fn'])
        _csv(output/'image_descriptors.csv',image_rows,list(image_rows[0]) if image_rows else ['dataset','member'])
        _csv(output/'gt_object_descriptors.csv',object_rows,sorted({k for r in object_rows for k in r}) if object_rows else ['dataset','member'])
        if project_root is not None:
            for source,dest in [('configs/phase07_experiment_matrix.json','experiment_matrix.json'),('docs/phase07_experiment_matrix.md','phase07_experiment_matrix.md')]:
                if (Path(project_root)/source).is_file(): shutil.copy2(Path(project_root)/source,output/dest)
        _write_report(output,summary,records,image_rows,object_rows)
        _json(output/'artifacts.json',[{'path':str(p.relative_to(output)),'sha256':file_digest(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifacts.json'])
    if summary['status']!='complete': raise RuntimeError(summary['error'])
    return output,summary
