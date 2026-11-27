# Faz 07 — Kontrollü eğitim hazırlığı

Bu teslim gerçek eğitim başlatmaz. [Notebook 07](../notebooks/07_hit_uav_controlled_training.ipynb) varsayılan **Tümünü çalıştır** akışında gerçek baseline kanıtlarını doğrular, özgün train/val kopyasını hazırlar, dört kolu dondurur ve GPU varsa sınırlı bellek preflight yapar. Eğitim kapısı `ENABLE_TRAINING=False` kalır. Kaynak ZIP, önceki model/run/raporlar ve `web/` değiştirilmez; test ve WiSARD görüntü/etiketleri açılmaz.

## Gerçek kanıt incelemesi

27 Kasım 2026'da bağlı Drive üzerinden gerçek `run_yolo11s_20261120T151540Z_78fb2af9` klasöründeki `ultralytics/train/args.yaml`, `effective_train_arguments.json`, `optimizer_effective.json`, `run_summary.json` ve `dataset_manifest.json` okundu. Tamamlanan Faz 06'nın `error_analysis_report.md`, `phase06_summary.json` ve val manifesti de incelendi. Bu, yeni model çıkarımı değildir. Raw deney dosyaları repoya eklenmedi.

Kaynaklar: [baseline klasörü](https://drive.google.com/drive/folders/1vx4ZvBpTt9TEQNF0erdi0Qd0OzZTgwH3), [Faz 06 klasörü](https://drive.google.com/drive/folders/14wVEO0eyTF9q3bVyMGjNl3bbRRGPUj1j). Drive erişim izni gerekir.

| Ayar | Gerçek kayıt | Yeni ortak blok |
|---|---|---|
| Model başlangıcı | Pretrained YOLO11s; SHA256 aşağıda | Aynı orijinal pretrained dosya; eski fine-tuned best.pt kullanılmaz |
| Optimizer | args=`auto`; gerçek sınıf **AdamW** | Açık `optimizer=AdamW`; runtime grupları doğrulanır |
| LR / betalar | args lr0=.01, momentum=.937; gerçek initial LR=.002, betas=(.9,.999), eps=1e-8 | lr0=.002, momentum=.9, beta2=.999; eps runtime kontrolü |
| Weight decay | Gruplar: bias=0, weights=.0005, normalization=0 | Aynı gruplar; nbs ölçekleme doğrulanır |
| Scheduler | cos_lr=False, lrf=.01 | Aynı doğrusal LambdaLR politikası; erken durma son LR'yi etkiler |
| Warmup | 3 epoch; warmup_momentum=.8; args bias_lr=.1 → etkin bias_lr=0 | Etkin bias_lr=0 korunur. AdamW betaları momentum-key warmup ile değiştirilmez |
| Batch / nbs | 8 / 64; nominal accumulation=8 | Ortak aday batch=4 / nbs=64; nominal accumulation=16. Warmup'ta 1→16 native interpolasyonu bütün kollarda aynıdır |
| Epoch / patience / seed | 40 / 10 / 42 | 40 / 10 / 42 |
| Hassasiyet | amp=False, half=False | FP32; AMP sessizce açılmaz |
| Augmentasyon | scale=.5, mosaic=1, close_mosaic=10; diğer tüm etkin ayarlar okunur | Test edilen tek faktör dışında etkin baseline argümanları aynen taşınır |
| Diğer | deterministic=True, rect=False, multi_scale=False, workers=2, cache=False | Aynı ortak ayarlar |
| Ortam | Ultralytics8.3.228; Torch2.14.1+cu130; torchvision0.29.1+cu130; Python3.13.16; Tesla T4 (15,637,086,208 bayt) | Ultralytics8.3.228 zorunlu; mevcut CUDA uyumlu Colab Torch kullanılır. GPU/yazılım kimliği yeni blokta ilk preflight ile kilitlenir |

Torch'un tarihi sürümüne veya aynı GPU'ya gelecekte erişim garanti değildir. Yeni ortamın tarihi baseline'dan farkı kaydedilir; eski baseline ile bit düzeyinde yeniden üretim iddiası yapılmaz. Aynı yeni blok içindeki kollar ve devamlar GPU/yazılım değiştiremez; değişirse yeni ortak blok gerekir.

Baseline manifesti SHA256 `689b69e20c0cb4ba79635adf6012918e7c7edd5ee6df2027e5e3373f7ed5f689` olarak yeniden hesaplandı ve run özetiyle eşleşti. Filtrelenmiş train **1933 görüntü/7430 Person**, val **282/1114**; Person arka planları 831 ve 114. Train dışlaması 75 DontCare +21 sıfır-ham; val dışlaması 5+3. Val üyeleri ve görüntü hash'leri Faz 06 manifestiyle aynı. Sınıf ve DontCare politikası değiştirilmez. Politikanın tarihsel `evaluation_scope` alanı eski baseline test kapsamıdır; bu hazırlığın gerçek kapsamı `selected_splits=[train,val]` ve `preparation_scope=original_train_val_only_no_test_images_or_annotations_read` alanlarıdır.

| Gerçek dosya | Yerelde yeniden hesaplanan SHA256 |
|---|---|
| args.yaml | e553d25b9070ec90e4856db8a2d3db0a21da7dea1b2060bea4a50545b8e6f64f |
| effective_train_arguments.json | b4aa0b2c02f4e4b0d4ddc62addc33f250221c51a07d4db6b8f45921e911a80c1 |
| optimizer_effective.json | ae239873dc60b91ed550fbc71b655f6d20d7ed45f29c3d001f8d8aef92062c4a |
| run_summary.json | b699ef3802db89e6d6bc64168ff3aeea6eff04b01e25eca43df8d014503f46a2 |
| Faz 06 val manifesti | 8ff4f9572917c6efd0f3924784b2b951766d22c78e279439999651f642836bdd |

İlk pretrained SHA256 `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5` ve kaynak ZIP SHA256 `5fed15d2ff895afb16c0ca328ea19353f416d7543e6f39ba54e44ca26c538555` gerçek run kayıtlarından okunmuştur; ağırlık/ZIP bu geliştirme ortamına indirilmedi ve burada yeniden hash'lenmedi. Colab hazırlığı bu dosyaların gerçek byte hash'lerini zorunlu olarak yeniden kontrol eder. Eksik dosya, eksik etkin ayar, bilinmeyen args farkı, optimizer grubu veya üyelik uyuşmazlığında durur.

Faz 06 run `run_phase06_20261127T152934Z_2071fdaa` raporu kaynak val mAP50=.8993149862, mAP50:95=.4925293100; fixed 996 TP/289 FP/118 FN; both<16 recall166/206; IoU[.30,.50) 48 FN ve 59 duplicate adayı bildirir. Bunlar yeni Faz 07 sonucu değildir. WiSARD'ın eski .1453 mAP50 sonucu bir domain-shift tanılamasıdır; deney, threshold veya seed seçmez.

## Dondurulan karşılaştırmalar

Mevcut [matris](phase07_experiment_matrix.md) ve JSON korunur. Yeni kontrol eski batch8 run ile bir köprü kontrolüdür; çözünürlük/augmentasyon etkisini eski run'a doğrudan bağlamaz.

| Kol | imgsz (train/val/predict) | scale | mosaic | C0'dan değişen ana faktör |
|---|---:|---:|---:|---|
| P07-C0 | 640 | .5 | 1 | Yok |
| P07-A1 | 640 | .25 | 1 | Scale aralığı |
| P07-A2 | 640 | .5 | 0 | Mosaic olasılığı |
| P07-R1 | 960 | .5 | 1 | Sistem çözünürlüğü politikası |

Kontrolde aday değer zaten aynıysa kol atlanır. R1 sensör bilgisi eklemez ve train/val/inference boyutunu birlikte değiştirir; yalnız öğrenilmiş temsil etkisi değildir. Ana seçim filtered kaynak-val native mAP50:95; checkpoint native kaynak-val fitness ile seçilir. Sabit conf=.25, eşleme IoU=.50, NMS=.70, max_det=300 korunur. Native mAP tabanı=.001; tanılama TP/FP/FN ile ayrı tutulur. Native son değerlendirme batch=1/rect=True/FP32 bütün kollarda sabittir; eğitim içindeki native val 2×ortak-batch politikası kullanır. Küçük nesne grupları **orijinal GT piksellerinde** width<16, height<16, both<16 olarak aynı paydalarla hesaplanır.

Eğitim esnasındaki val `conf=None` varsayılan native yolla kalır; son mAP geçişi .001'i açık verir. Native eğri-optimum P/R, fixed .25 P/R değildir. Native rectangular padding, tek-image predict minimum-stride padding, NMS ve farklı eşleme algoritmaları önceki Faz 06 sınırlılıklarıyla birlikte raporlanır. Kaynak val defalarca kullanılmıştır ve splitler arası yakın-kare sızıntısı riski sürer. WiSARD zaten incelenmiştir; final saha iddiası için yeni bağımsız uçuş/saha/görev kümesi gerekir.

## GPU preflight ve bellek politikası

640→960 kare tensor piksel oranı 2.25'tir; kesin VRAM gereksinimi değildir. **Bu ortamda GPU belleği veya uygun batch ölçülmedi.** Ortak batch4 başlangıç adayıdır; minimum GPU modeli/VRAM garantisi verilemez.

Colab GPU'da her aktif kol için iki gerçek augmented train batch'inde forward/loss/backward yapılır, AdamW moment buffer maliyeti ayrılır; optimizer.step veya eğitim döngüsü yoktur. Geçici model/BatchNorm durumları atılır, ilk dosya değiştirilmez. 2×batch sentetik kare tensor eval forward maliyeti de ölçülür. Peak allocated/reserved, başlangıç free/total ve örnek train dosyaları kaydedilir. %20 free-memory payı istenir; yoğun GT, farklı augmentasyon, optimizer çalışma alanı ve uzun dönem allocator davranışı nedeniyle yine OOM olabilir. Bu bir kaynak-sample uygunluk kontrolüdür, tam eğitim garantisi değildir.

Herhangi bir kol başarısızsa bütün blok eğitim için kapalıdır. **Bütün kollar için** batch2 veya batch1 ile yeni blok hazırlayıp C0 dahil tüm ölçümleri tekrarlayın; eski sonuçları silmeyin. nbs=64 korunur, nominal accumulation sırasıyla32/64 olur. Bunlar yeni ortak kontrol bloklarıdır. Per-arm auto-batch ve OOM retry yasaktır. Eğitimde OOM görülürse aynı bloğun kalan kolları da durur.

## Colab talimatları

1. PR birleştikten sonra [Notebook 07'yi Colab'da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/07_hit_uav_controlled_training.ipynb).
2. **Çalışma zamanı → Çalışma zamanı türünü değiştir → GPU**, ardından **Tümünü çalıştır**. İlk Drive iznini verin. Varsayılan baseline/ZIP yolları önceden kullanılan Drive konumlarıdır; elle optimizer/regex doldurulmaz.
3. Son `prepared_not_trained` planını ve preflight durumunu inceleyin. GPU yoksa hazırlık yapılır, preflight bloke kalır; CPU eğitimi başlamaz. Eksik gerçek kanıt ise tanılama raporu ile durur.
4. Bu fazda `ENABLE_TRAINING=False` bırakılır. Sonraki gerçek eğitim ayrıca yetkilendirildiğinde kapı açılabilir. Aktif kollar sırasıyla ayrı attempt dizinlerine yazılır; doğrulanmış ortak plan ve GPU preflight olmadan eğitim başlamaz.
5. Kesintiden sonra aynı blok için `RESUME_BLOCK` yolunu (veya `THERMA_PHASE07_BLOCK`) verin. Geçici veri yoksa sadece özgün train/val aynı hash'lerle yeniden hazırlanır. Preflight aynı GPU/yazılımla tekrar çalıştırılır. Sonraki yetkili çalıştırıcı tamamlanan kolu atlar, yarım kolu mühürlü snapshot'tan yeni attempt içinde sürdürür. Eğitim bitip değerlendirme kesilmişse yalnız değerlendirmeyi yeni attempt'te tekrarlar.

Çıktı kökü: `/content/drive/MyDrive/ThermaSearchAI/runs/hit_uav_phase07/run_phase07_<UTC>_<uuid>/`. Geçici kopya `/content/therma-phase07-work/` altındadır. Model/veri indirilmez; sadece kod ve paket kurulumu yapılır. Ağırlıklar repoya commit edilmez.

## Kesinti güvenliği ve çıktılar

`frozen_plan.json` hash'i, tam baseline kanıt hash'leri, `baseline_evidence.json`, `dataset_manifest.json`, `preparation_status.json`, `preparation_report.md`, kol başına `arm_specification.json` ve her preflight'ın `memory_preflight.json` dosyası ayrı kaydedilir. Metrikler henüz null'dır; sentetik testler gerçek başarı olarak sunulmaz.

Yetkili eğitimde kol başına eşsiz `attempts/attempt_<UTC>_<uuid>/` altında checkpoint'ler, Ultralytics `args.yaml/results.csv`, runtime `effective_train_arguments.json`, `optimizer_effective.json`, mühürlü epoch snapshot'ları, durum/hata/süre ve GPU bellek kaydı tutulur. Bütün epoch'ların kopyaları Drive alanı tüketir; geçmiş otomatik silinmez. Native eğriler/PR/confusion çıktıları, `validation_metrics.json`, `per_image_metrics.csv`, `val_predictions.jsonl`, küçük nesne paydaları, FP/image ve gecikme kayıtları değerlendirme sonrası oluşur. Latency 5 warmup + deterministik 20 val örneği, batch1, CUDA synchronize ile uçtan uca ölçülür; görüntü okuma/preprocess/NMS/host transfer dahildir, saf ağ zamanı değildir. Kısa liste ve seed42/43/44 tekrarları ayrı sonraki karardır; en iyi seed seçilmez.

Her snapshot exclusive dizine kopyalanır, dosyalar hash'lenir ve `complete.json` en son yazılır. Tamamlama işareti olmayan yarım kopya resume adayı sayılmaz; son mühürlü snapshot kullanılır. Son mühürlü snapshot bozuksa hata verilir, daha eski mühürlü epoch'a sessizce geçilmez. Resume checkpoint'inin gömülü eski `project/save_dir/data` yolları yeni attempt'e yönlendirilir; ayar sapması dosya yazmadan reddedilir. Önceki en iyi checkpoint ve early-stopper durumu taşınır. Native Ultralytics resume EMA ve FP16 optimizer-state kullanır, RNG/dataloader durumunu tam restore etmez; **kesintisiz eğitime bit düzeyinde eşit değildir**. Devam edilen kol/karşı kontrol için bu sınırlılık ve bütün attempt'ler raporlanmalı; kritik karşılaştırmada kesintisiz eşlenmiş tekrar tercih edilmelidir. Stale `active.lock` otomatik kaldırılmaz; başka eğitim olmadığının elle incelenmesi gerekir.

Gerçek CUDA trainer özel API uyumu, uzun eğitim/resume ve son metrik/grafik üretimi bu ortamda çalıştırılmadı. Sabit Ultralytics sürümüne bağlı kod, sentetik birim/mock notebook testleriyle doğrulandı; gerçek uygunluk Colab preflight ve sonraki yetkili eğitimde doğrulanacaktır. [Gerçek kontrol komutları](validation_phase07.md).
