# Phase 05 doğrulama kaydı

Tarih: 2026-11-24. Gerçek checkpoint ve WiSARD ZIP’i bu geliştirme ortamında mevcut değildir. Gerçek model çıkarımı, gerçek mAP/Recall ölçümü veya eğitim yapılmamıştır. Aşağıdaki sentetik sonuçlar gerçek model başarımı değildir.

## Çalıştırılan kontroller

- `.venv/bin/python -m unittest discover -s tests -q`: **108 test geçti**: mevcut 90 test korunur, Phase 05 için 18 sentetik test eklendi. Annotation parsing, IR-only filtreleme, boş anotasyon dışlaması, eşleme, metrikler, küçük nesne paydaları, dosya çıktıları ve başarısızlık tanılaması kapsanır.
- `.venv/bin/python tests/validate_wisard_external_notebook.py`: Notebook 05 nbformat şeması ve bütün hücreler sentetik model/veri ile doğrulandı. Ayrıca eksik checkpoint ve bozuk IR etiketi senaryolarında beklenen hata ve kalıcı raporlar denetlendi. Public bootstrap ve Drive OAuth yerel doğrulamada atlanır; model, ortam bilgisi ve native mAP yalnızca test kernel’inde mock edilir. Üretim kodunda gerçek metrik yerine sentetik değer koyan bir seçenek yoktur.
- `.venv/bin/python tests/validate_notebook.py`: Notebook 01 varsayılan/verisiz ve sentetik üç split akışları geçti; 12 görsel çıktı.
- `.venv/bin/python tests/validate_real_audit_notebook.py`: Notebook 02 mevcut sentetik audit/sızıntı akışı geçti; 5 temel PNG, contact sheet/manüel CSV, 8 exact ve 4 near aday korundu.
- `.venv/bin/python tests/validate_wisard_notebook.py`: Notebook 03 bilinen örnek, bilinmeyen ZIP ve eksik ZIP sentetik senaryolarında geçti.
- `.venv/bin/python tests/validate_training_notebook.py`: Notebook 04 mevcut sentetik dönüşüm/mocked eğitim/best/test akışı geçti; gerçek eğitim başlatılmadı.
- `.venv/bin/python -m compileall -q src tests` ve `git diff --check` çalıştırıldı.

Yeni testler: yalnızca IR üyesi okunduğunu doğrulayan spy ve bilerek bozuk VIS; bağımsız kaynak/Person/boş TXT sayımları; geçersiz format/NaN/sınır/sınıf/eksik TXT; bozuk görüntü/boyut; duplicate kutu/kare ve count.txt uyuşmazlığı; global bire bir eşleme, duplicate prediction FP ve missed GT FN; 16 piksel kesin sınırı ve orijinal normalize ölçümün korunması; explicit GT paydalı küçük recall; tüm tahminler boşken Precision=null ve Recall=0; native mAP ile fixed P/R ayrımı; native GT/görüntü payda uyuşmazlığında skor reddi; gerçek girdilerin hash’leri; sentetik model dosyası değiştirilirse skor geçersizliği; önceki run’ın korunması; 200 DPI PNG, CSV/JSONL/rapor üretimi; missing/malformed girdide model yüklememe ve metriklerin null kalması.

Sentetik küçük nesne yakın planı, TP/FP/FN-küçük recall özeti, belirsiz boş anotasyon contact sheet’i ve confidence/IoU histogramı dosyadan açılıp incelendi. Başlıklar, eksenler ve GT/prediction renk ayrımı okunabilir. Bu görseller yapay veri/test çıktılarıdır. Çıktılar `outputs/validation/wisard_external/` altında Git dışında tutulur; kaynak notebook çıktısızdır.

## API incelemesi ve sınırlar

Sabit Ultralytics 8.3.228 kaynak wheel’i üzerinden `check_det_dataset` için train/val YAML anahtarları (train:null), native eğri dizilerinin plots=False ile hesaplanması ve `nt_per_class` / `nt_per_image` paydaları incelendi. Native mAP GT ve pozitif görüntü sayıları, aynı IR manifestiyle eşleşmek zorundadır. Bu kaynak incelemesi gerçek PyTorch/Ultralytics CPU/CUDA çıkarım testinin yerine geçmez.

Public repo ayrı bir yerel dizine clone/fetch/checkout edilerek `36f11b97f1d998873773ed2524b57e850c727847` yardımcı kod revizyonu ve hafif evaluator import’u doğrulandı. Paket kurulumu, gerçek checkpoint veya veri indirmesi/çıkarımı çalıştırılmadı. Notebook bu revizyona sabitlendikten sonra üç sentetik senaryosu tekrar geçti.

Verilen gerçek yollar dosya sistemi üzerinden kontrol edildi ve mevcut bulunmadı:

- `/content/drive/MyDrive/ThermaSearchAI/runs/hit_uav_yolo11s/run_yolo11s_20261120T151540Z_78fb2af9/best.pt`
- `/content/drive/MyDrive/ThermaSearchAI/datasets/WiSARD_Multi_Modal_Sample.zip`

Gerçek Google Drive OAuth, güncel Colab torch/torchvision/CUDA uyumu, gerçek checkpoint yükleme ve WiSARD görsellerindeki gerçek çıkarım/metrikler sınanmadı. 264/1006/3 kullanıcı referansları bu geliştirme çalışmasının yeni ölçümü değildir. Gerçek sonuçlar yalnızca Notebook 05’in gerçek girdilerle çalıştırılmasından sonra oluşacaktır. Model/dataset indirmesi, eğitim, source split değişikliği, VIS değerlendirmesi veya frontend değişikliği yapılmadı.
