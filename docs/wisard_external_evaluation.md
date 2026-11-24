# Phase 05 — WiSARD IR zero-shot external evaluation

Notebook 05 evaluates the **existing** HIT-UAV-trained YOLO11s Person checkpoint on WiSARD IR. No retraining, fine-tuning, weight saving, checkpoint/dataset download, VIS image reading, pairing or synchronization is performed. This is a limited external stress test, not proof of independent-mission generalization.

## Exact Colab execution

After merging the PR, open [Notebook 05 in Colab](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/05_wisard_external_evaluation.ipynb). Choose a GPU runtime if available, then **Runtime → Run all**. CPU inference is supported when CUDA is unavailable and is recorded explicitly; it can take longer. Approve Google's first Drive mount prompt. No cell edits or threshold selection are needed.

The defaults are:

- Checkpoint: `/content/drive/MyDrive/ThermaSearchAI/runs/hit_uav_yolo11s/run_yolo11s_20261120T151540Z_78fb2af9/best.pt`.
- ZIP: `/content/drive/MyDrive/ThermaSearchAI/datasets/WiSARD_Multi_Modal_Sample.zip`.
- Persistent output root: `/content/drive/MyDrive/ThermaSearchAI/reports/wisard_external_eval/`.
- Temporary prepared IR copies: `/content/therma-external-eval-work/<run_id>/ir_eval/`.

Both inputs must already exist. Missing inputs raise explicit errors and leave a new run's diagnostic JSON/Markdown/CSV files; no substitute model or archive is selected. The notebook installs the existing pinned runtime `ultralytics==8.3.228` from `requirements-training-colab.txt`, reusing Colab's torch/torchvision installation. Runtime-package and public-code installation is separate from model/data download. The notebook's helper-code Git revision is pinned and the actual checked-out commit is recorded.

## Source validation and filtering

`wisard_external_data.py` reuses `WisardArchive`, `sample_identity` and `parse_sample_labels` from the established WiSARD adapter. Only images inside `210417_MtErie_Enterprise_IR_0004/` are opened. The VIS subtree is not decoded, read for labels, paired or synchronized. Computing SHA256 over the complete ZIP naturally includes its compressed bytes; this is an archive identity check, not VIS analysis.

Every IR image must have the verified eight-digit trailing frame token, a unique frame key and a corresponding same-stem TXT. One unambiguous IR root is required. Actual image decoding verifies 640×512 dimensions, L/RGB mode, no EXIF orientation transform, and the archive reader's size/path/CRC limits. RGB mode alone is not used to infer modality. Bad JPEG termination is rejected instead of allowing the framework to repair a prepared image implicitly.

Five-column normalized YOLO labels must contain finite positive boxes within image bounds and class ID 0 (Person, based on previous user-verified sample semantics). Unknown classes, malformed rows, missing/orphan labels, duplicate GT/frame keys, corrupt images or inconsistent available count.txt records are explicit diagnostic errors. Any such error blocks **all** scoring; a supposedly cleaned subset is not silently evaluated. Valid input bytes are copied into a new temporary work directory, leaving the source ZIP and original labels unchanged. No split is added to or modified in the source dataset. The local YAML uses `train: null`; `val`/`test` are framework aliases to the same scored IR subset, not new experimental splits.

A whitespace-empty TXT is uncertain, not a verified negative. Such images are **excluded by default**, listed in `exclusion_manifest.csv`, and shown in paginated 200 DPI review contact sheets. Their original images and labels are not changed and they do not enter either mAP or fixed-threshold inference. The protocol contains no option to silently treat them as verified negatives. If all IR images are uncertain or invalid, evaluation stops without fabricated zero metrics.

Historical user references — 264 IR images, 1006 Person annotations and three empty TXT files — are stored separately and independently recalculated. A reference mismatch is reported as a mismatch, not repaired by replacing the new count. Input counts on an invalid archive may be partial and are marked by `input_validation_passed=false`.

## Frozen model and two separate metric procedures

The loader accepts an existing trusted `.pt` with `{0: 'Person'}` names. It never receives a downloadable model name. The evaluator calls only `val` and `predict`; there is no training, optimizer, fine-tuning or model-save call. In-memory inference fusion is allowed, while checkpoint bytes are checked unchanged at completion. ZIP hashes and included prepared image/label hashes are also verified again.

All settings are fixed before WiSARD inference:

| Setting | Value |
|---|---:|
| Image size | 640 |
| Fixed diagnostic confidence | 0.25 |
| Custom matching IoU | 0.50 |
| NMS IoU | 0.70 |
| Maximum detections | 300 |
| Native mAP confidence floor | 0.001 |

The configuration rejects threshold changes in this Phase 05 protocol. There is no search for a WiSARD-optimal operating threshold. Device is CUDA:0 if available, otherwise CPU; native evaluation batch is 8 on CUDA (4 below 6 GiB total memory), 1 on CPU. Native evaluation uses FP32 and workers=0, and records these choices.

**Ultralytics mAP:** `model.val(split='test', conf=.001, ...)` independently computes mAP@50 and mAP@50:95 on exactly the included IR images. The native GT and positive-image denominators must match the validated IR manifest, otherwise all scoring fails (detecting silent skipping/deduplication). Native metric arrays are exported into readable 200 DPI curves and saved numerically. Native P/R values may use a curve-optimum confidence; they are retained as framework diagnostics, not used as fixed-threshold Precision/Recall. Native plotting is disabled; report curves are rendered by the new figure module at 200 DPI. If native curves are unavailable (for example, no detections), availability is explicitly false rather than inventing a curve.

**Fixed-threshold metrics:** the existing `predict_person` and `match_person_predictions` functions use confidence=.25 and IoU=.50. Predictions are matched in descending confidence order to the highest-IoU unmatched GT, one-to-one. A duplicate prediction is FP; unmatched GT is FN. TP/FP/FN and micro Precision/Recall are aggregated over all scored images, rather than averaging per-image ratios. No predictions makes Precision undefined (`null`); nonempty GT with no detections has Recall=0. True negatives are undefined for object detection and labeled N/A in the confusion matrix.

`FP / evaluated image = total FP / included image count`. Because uncertain empty scenes are excluded, this is a conditional statistic on the scored annotated subset, not an unconditional false-alarm rate on verified negative scenes.

## Small objects, localization and domain shift

GT widths/heights are measured in **original IR pixels** from normalized label dimensions multiplied by actual image dimensions. The code preserves those measured sizes instead of relying on subtracting reconstructed corners near the 16-pixel boundary. Three overlapping groups use strict comparisons:

- width <16 pixels;
- height <16 pixels;
- width <16 and height <16 pixels.

Each group reports total GT denominator, detected GT, missed GT and recall. A zero-GT group has recall=null. All groups reuse the **same global one-to-one matching**; GTs are not rematched separately to inflate a subgroup's recall, and group denominators must not be summed.

Localization is described by matched TP IoUs and best prediction IoU for every GT (zero if no prediction). TP IoU is conditional on already detected objects and is biased toward easier cases. Best IoU per GT does not impose one-to-one assignment and is descriptive, not another recall or mAP score. Measured GT pixel-size summaries support domain-shift interpretation, but no causal attribution to sensor/scene/object size is claimed without matched source-domain evidence.

The MtErie sample is reported to contain temporally correlated frames from one flight. Image counts do not represent independent missions; no independent-frame confidence interval is asserted. HIT-UAV's filtered test protocol and WiSARD's IR/exclusion protocol differ, so their numbers must not be presented as interchangeable benchmark scores. The prior training run ID is a user-supplied provenance reference, not a newly verified training result. Annotation completeness and uncertain negatives remain limitations.

## Outputs and figures

Every run creates a new `run_wisard_external_<UTC>_<uuid>/` directory, preserving all prior outputs. It contains:

- `evaluation_summary.json`, `evaluation_report.md`;
- `per_image_metrics.csv`, `exclusion_manifest.csv`, `predictions.jsonl`;
- `data_manifest.json`, source member hashes and prepared data YAML;
- `input_hashes.json` (before/after model and ZIP SHA256), `reproducibility.json` (Git/Python/PyTorch/Ultralytics/device/configuration);
- native mAP metrics/curve arrays and optional framework JSON predictions;
- 200 DPI figures, `figure_manifest.json`, `artifacts.json` with output sizes/SHA256.

`predictions.jsonl` contains the fixed-threshold predictions, original image dimensions, GT boxes/sizes, ZIP member identity and matching indices. Native mAP predictions are separate and have the .001 confidence floor. Partial failed-run files must not be interpreted as a completed model evaluation; top-level performance metrics remain null on failure or an input-hash change.

Figures include red GT boxes, blue matched predictions, magenta FP and orange dashed FN; deterministic full-image examples; contextual small-person zooms with original pixel-size labels; confidence distributions at >=.25; TP localization histogram; fixed-count/small-recall summaries; confusion matrix; native mAP-derived curves; and excluded-empty review sheets. At most four examples per category are distributed over eligible frame order. Examples are inspectable evidence, not a representative statistical sample. A category with no examples has no example figure, rather than an invented example.

Prepared full-size IR images remain in Colab's temporary work root and can be recreated from source member/hash records. Generated review/evaluation figures are automatically saved to Drive. No weights, ZIPs, source images, credentials or generated experiment artifacts are committed. Existing notebooks, model runs, reports and `web/` are unchanged.
