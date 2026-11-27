# Notebook 06 — HIT-UAV kaynak-validation hata analizi

Bu faz eğitim yapmaz. Mevcut checkpoint’i özgün HIT-UAV validation splitinde, Phase 04’ün aynı Person-only/DontCare/sıfır-ham-anotasyon politikasıyla inceler. WiSARD sadece önceden görülmüş rapor bağlamı ve isteğe bağlı **piksel/GT betimlemesidir**; WiSARD model çıkarımı veya model/threshold seçimi yapılmaz.

## Colab çalıştırma

PR birleştikten sonra [Notebook 06’yı Colab’da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/06_hit_uav_error_analysis.ipynb). Tercihen GPU seçip **Çalışma zamanı → Tümünü çalıştır** deyin; CPU çıkarımı desteklenir. Google’ın ilk Drive izni gerekebilir. Hücre/regex/etiket şeması düzenleme veya eğitim komutu yoktur.

Varsayılan girdiler:

- `/content/drive/MyDrive/ThermaSearchAI/runs/hit_uav_yolo11s/run_yolo11s_20261120T151540Z_78fb2af9/best.pt`
- `/content/drive/MyDrive/ThermaSearchAI/datasets/hit_uav_v1.2.1.zip`
- Betimsel karşılaştırma için varsa `/content/drive/MyDrive/ThermaSearchAI/datasets/WiSARD_Multi_Modal_Sample.zip`

Yeni raporlar `/content/drive/MyDrive/ThermaSearchAI/reports/phase06_error_analysis/run_phase06_<UTC>_<uuid>/` altındadır. Yerel hazırlanmış görüntüler `/content/therma-phase06-work/` altında geçicidir. Her çalışma yeni dizin oluşturur; eski run/rapor/etiket/checkpoint üzerine yazılmaz. Mevcut Ultralytics 8.3.228 paketi ve sabit Git revizyonu kullanılır. Model/veri indirilmez.

## Kaynak veri ve yöntem

Mevcut `prepare_hit_uav_yolo(..., splits=('val',))` yolu kullanılır. Varsayılan üç split davranışı Notebook 04 için korunur; `validate_prepared_dataset` hem tarihsel üç-split manifestini hem val-only manifestini doğrular. Yalnız `annotations/val.json` ve val görüntüleri okunur; train/test görüntüsü veya test metriği analiz edilmez. ZIP tümüyle checksum için okunabilir; bu dosya kimliği kontrolüdür, test verisiyle model seçimi değildir. ZIP kök keşfi tüm üye adlarının envanterini kullanır.

Özgün validation üyelerinden sıfır **ham** anotasyonlu ve DontCare içeren görüntüler dışlanır. DontCare içindeki Person kutularının kaybı ve her dışlama sayısı raporlanır. Diğer bilinen sınıfların kutuları hedef dışıdır; diğer-sınıf-only görüntülerde boş Person etiketi önceki politika gereği korunur, Person etiket tamlığı varsayımı açık tutulur. Bozuk kayıt, sınıf/referans/sınır hatası veya hazırlanan dosya/hash uyuşmazlığı analizi durdurur. Kaynak etiketler kırpılmaz/değiştirilmez. Eğitim manifestindeki tarihsel `evaluation_scope` alanı baseline test etiketidir; bu yeni çalışmanın gerçek kapsamı `selected_splits=['val']` ve `analysis_scope=filtered_original_HIT_UAV_validation_only` ile açıkça kaydedilir.

Checkpoint’in yanında önceki `dataset_manifest.json` varsa policy, val üyeliği ve görüntü hash’leri doğrulanır; uyuşmazlıkta durur. Dosya yoksa önceki politikaya göre yeniden üretildiği fakat gerçek run üyeliğiyle bağımsız kıyaslanamadığı yazılır. Paketin bildirdiği checkpoint hash’i ile gerçek girdi hash’i eşitliği ayrı kaydedilir; eşit değilse WiSARD sonuçlarının aynı modele ait olduğu varsayılmaz.

Validation bu baseline checkpoint’inin seçimi/erken durdurmasında daha önce kullanılmıştır. Buradaki kaynak skorlar bağımsız, tarafsız final test performansı değildir. Önceki splitler arası dHash/sekans sızıntısı riski de devam eder; bu PR splitleri yeniden bölmez.

## Hata kategorileri

Fixed geçiş confidence=.25, eşleme IoU=.50, imgsz=640, NMS IoU=.70, max_det=300 kullanır. Confidence azalan sırada bire bir eşleme aynen korunur. Per-image TP/FP/FN ve küçük nesne recall paydaları kaydedilir.

Her FN, tüm fixed tahminler arasındaki en yüksek IoU; her FP, tüm GT’ler arasındaki en yüksek IoU ile şu bölümlere ayrılır: sıfır örtüşme, (0,.10), [.10,.30), [.30,.50), ≥.50. Sıfır örtüşme GT’ye göre tanımlıdır, görüntüde hiç tahmin yok demek değildir. ≥.50 FP ve önceden eşlenmiş GT çakışması duplicate **adayıdır**; fiziksel kimlik doğrulaması değildir. FN≥.50, örtüşen GT/eşleme çakışması gibi durumları ayrı görünür kılar.

Native val conf tabanı=.001 ile ayrı çalışır. Export’taki image_id açık dosya gövdesi eşlemesiyle çözülür; class ID veya frame eşlemesi tahmin edilmez. Native JSON pixel xywh, fixed JSONL pixel xyxy’dir. Serialization nedeniyle sıfır genişlik/yüksekliğe yuvarlanan native kutular sıfır IoU’lu aday olarak korunur; negatif/sonlu olmayan geometri veya bilinmeyen ID hata üretir. Her fixed FN’nin native en iyi-IoU adayına bakılır; bir native aday birden fazla GT’yi kapsayabilir. Düşük güvenli aday sayıları **recoverable TP değildir**; threshold önerisi yapılmaz.

## Native / fixed tutarlılık incelemesi

Native mAP, .50:.95 IoU dizisinde IoU-tabanlı eşsiz eşleme kullanır. Custom matcher confidence-tabanlı greedy .50 eşlemesidir. Native eğri-optimum P/R, fixed conf=.25 P/R değildir. Bu metrikler aynı isimlerle birbirinin yerine kullanılamaz.

Ultralytics 8.3.228 native validation rectangular batch dataset pad=.5 kullanır; tek-image predict minimum stride padding kullanabilir. Aynı imgsz, aynı tensor boyutu anlamına gelmez. Callback ile native `batch_shapes`, `seen`, JSON tahmin sayısı ve etkin args; predictor’dan mevcut etkin rect/half/imgsz/device ayarları kaydedilir. Fixed `imgsz` alanı hedef boyuttur, gerçek inference tensor şekli olarak sunulmaz. İki geçişte nominal pixel/255 ölçeklemesi ve BGR→RGB model dönüşümü kütüphanenin işidir; ayrı betimsel Pillow L dönüşümü **model girdisine uygulanmaz**. Native FP32 açıkça seçilmiştir; farklı NMS adayları, batch/padding, dtype veya export score/box yuvarlaması uyuşmazlık yaratabilir. Tespit farkı tek başına bug kanıtı değildir.

Native GT sayısı ve **pozitif görüntü sayısı** manifestle denetlenir; diğer-sınıf-only arka planlar nedeniyle pozitif görüntü sayısı tüm scored görüntü sayısına eşit olmayabilir. Callback seen alanı mevcutsa toplam görüntü sayısı da kontrol edilir. Native export tamamen boşsa yalnız callback doğrulanmış sıfırla yok dosya kabul edilir; yok export sessizce sıfır skor sayılmaz.

## Yoğunluk, kontrast ve boyutlar

Kaynak val ve varsa geçerli nonempty WiSARD IR görüntülerinde tam görüntü 8-bit display-luminance mean/std, P05/P50/P95, P95−P05 ve 0/255 doygunluk oranları kaydedilir. Her GT için pixel genişlik/yükseklik, ROI mean/std ve çevre halkasına göre signed/absolute intensity farkı hesaplanır. ROI sınırları floor/ceil, çevre payı en az 4 piksel ve en büyük GT kenarının yarısıdır; GT dışındaki halka başka insan/nesne içerebilir.

L veya RGB termal gösterimler radyometrik sıcaklık değildir. Kamera tone mapping, sahne, anotasyon yoğunluğu, filtreleme ve ROI bağlamı karşılaştırmaları etkiler. Grafikler görüntü-level descriptor dağılımı ve GT boyutlarını gösterir; fiziksel sıcaklık/gerçek kontrast kalibrasyonu veya nedensel domain-shift açıklaması sunulmaz. WiSARD ZIP’i yoksa bu eksiklik belirtilir; mevcut paket sonuçları yeni ölçüm diye yazılmaz.

## Çıktılar

`phase06_summary.json`, `error_analysis_report.md`, kaynak val `source_val_predictions.jsonl`, `per_image_errors.csv`, `fn_errors.csv`, `fp_errors.csv`, `image_descriptors.csv`, `gt_object_descriptors.csv`, `protocol_runtime.json`, kaynak manifest/dışlama CSV/YAML, native export, 200 DPI PNG’ler, figür/artifact SHA256 manifestleri ve önerilen Phase 07 JSON/Markdown matrisi otomatik kaydedilir. Tamamlanmayan run’ın kaynak başarı metrikleri null kalır; kısmi dosyalar tanılamadır. Kaynakların before/after hash’leri kontrol edilir.

Paket değerlendirmesi: [phase06_evidence_review.md](phase06_evidence_review.md). Eğitim önerisi: [phase07_experiment_matrix.md](phase07_experiment_matrix.md). Gerçekte çalıştırılan kontroller: [validation_phase06.md](validation_phase06.md). WiSARD zaten incelenmiştir; final genelleme için bağımsız dış holdout ve doğrulanmış negatif sahneler gerekir.
