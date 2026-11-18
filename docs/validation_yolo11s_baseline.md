# İlk YOLO11s baseline altyapısı doğrulama kaydı

Tarih: 2026-11-18. Gerçek HIT-UAV ZIP’i, CUDA GPU, pretrained ağırlık veya model eğitimi bu geliştirme çalışmasında kullanılmamıştır. Aşağıdaki testler **gerçek model başarımı değildir**.

## Çalıştırılan kontroller

- `.venv/bin/python -m unittest discover -s tests -q`: **90 test geçti**: önceki 74 test korunur; 16 yeni dönüşüm, GPU kapısı, inference, sabit eşik tanılama ve mocked orchestration testi eklenmiştir.
- `.venv/bin/python tests/validate_training_notebook.py`: Notebook 04 nbformat şeması ve bütün hücreleri yapay HIT-UAV ZIP’i ile geçti. Public bootstrap/Drive atlandı, GPU ve YOLO yalnızca test kernel’inde mock edildi. Model ağırlığı yerine `SYNTHETIC, NOT A MODEL` byte’ları; metrik yerine açıkça sentetik değerler kullanıldı. Dönüşüm, dosya/manifest denetimi, train çağrısı, best checkpoint seçimi, sonradan tek ayrı test çağrısı, rapor/grafik/JSONL/CSV çıktıları sınandı. Üretim kodunda CPU eğitimi için bir test-bypass seçeneği yoktur.
- `.venv/bin/python tests/validate_notebook.py`: Notebook 01 veri bulunmayan ve sentetik üç split akışlarında geçti; 12 grafik/görsel çıktı.
- `.venv/bin/python tests/validate_real_audit_notebook.py`: Notebook 02 bütün hücreleri sentetik veride geçti; temel 5 PNG, contact sheet/manüel CSV, 8 exact ve 4 near aday doğrulandı.
- `.venv/bin/python tests/validate_wisard_notebook.py`: Notebook 03 bilinen sentetik örnek, bilinmeyen ZIP ve eksik ZIP senaryolarında geçti.
- `.venv/bin/python -m compileall -q src tests` ve `git diff --check` çalıştırıldı.

Yeni test kapsamı: piksel xyxy↔normalize YOLO ve kenar kutuları; NaN/negatif/sınır dışı koordinat/sınıf reddi; sıfır ham anotasyon ve DontCare dışlaması/Person kaybı; diğer-sınıf-only arka plan sayımı; kaynak ZIP hash ve split üyeliğinin korunması; bozuk kaynak ve boş Person splitinde eğitim kapısı; çıktı görüntüsü/etiket/YAML hash hatası ve fazla dosya; duplicate Person kutusu; gerçek Ultralytics labels/{split}.cache davranışı; GPU yokken durma ve düşük bellek batch kararı; inference JSON alanları; duplicate detection FP ve eşleşmeyen GT FN; sıfır tahminde tanımsız Precision; başarısız hazırlık/eğitimde model/test çağrılmaması; best checkpoint sonrasında ayrı test ve kayıtlar. Notebook bootstrap’ının GPU yokken clone/pip çağırmadan durması ayrıca sınanır.

Sentetik GT/prediction, FP örneği ve train/val loss PNG’leri dosyadan açılarak görsel incelendi; başlık/kutu/eksenler kontrol edildi. Tek epoch kaydında loss noktası da gösterilir. Bu görseller gerçek sensör/model sonucu değildir.

## Bağımlılık/API incelemesi

Ultralytics 8.3.228’in PyPI sürümü doğrulandı; yaklaşık 1 MB kaynak wheel’i API incelemesi için indirildi. `YOLO.train/val`, callback zamanlaması, `trainer.args.save_dir`, `best.pt`, sonuç CSV alanları, native metriklerin fitness’i, pretrained asset indirme yolu, Settings anahtarları ve label cache dosyası üretimi kaynak kodundan incelendi. PyTorch/Ultralytics bu ortama kurulmadı; pretrained model indirilmedi. Bu inceleme gerçek GPU entegrasyon testinin yerine geçmez.

Notebook 01–03, mevcut HIT-UAV/WiSARD analiz modülleri, veri dosyaları, eski raporlar ve frontend kodu değiştirilmedi. Eğitim bağımlılığı ayrı dosyadadır. Geçici sentetik çıktı/model dosyaları `outputs/validation/yolo_training/` altında ve Git dışında tutulur; kaynak notebook çıktı/sayaçları boştur.

## Sınanmayanlar ve bilimsel sınırlar

Gerçek Colab Drive OAuth, güncel Colab CUDA/PyTorch/torchvision uyumu, 40 epoch GPU eğitimi, gerçek pretrained ağırlık indirmesi, gerçek veri üzerinde Ultralytics yükleyicisi ve gerçek test skorları burada sınanmadı. Gerçek ZIP’in bütünlüğü/sayımı/Person veya DontCare sayısı bu ortamda yeniden ölçülmedi. Bunlar Notebook 04 çalıştırmasında üretilir. Dönüşüm politikası özgün splitleri yeniden bölmeden filtrelenmiş alt kümeler üretir; skor tam özgün HIT-UAV test skoru değildir. Kaynak dHash/sekans sızıntısı riski korunur; bağımsız saha genellemesi iddia edilmez.
