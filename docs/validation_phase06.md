# Faz 06 — Doğrulama kaydı

Tarih: 2026-11-27. Gerçek checkpoint, HIT-UAV ZIP’i ve WiSARD ZIP’i bu geliştirme ortamında mevcut değildir. Yeni gerçek model çıkarımı, kaynak-validation skorlaması veya GPU eğitimi yapılmamıştır. Önceki kullanıcı/WiSARD sonuçları yeni ölçüm olarak sunulmaz.

## Gerçekten çalıştırılan kontroller

- `.venv/bin/python -m unittest discover -s tests -q`: **124 test geçti**; önceki 108 test korundu, 16 yeni sentetik test eklendi. Son görsel/rapor düzenlemesinden sonra Phase 06’nın 16 testi ayrıca tekrar geçti.
- `.venv/bin/python tests/validate_phase06_notebook.py`: Notebook 06 nbformat şeması, bütün hücreleri sentetik kaynak/target ZIP ve mocked frozen model ile geçti. Eksik checkpoint senaryosunda beklenen hata ve kalıcı başarısız run raporu doğrulandı. Yeni rapor/görsel düzenlemesi sonrasında tekrar geçti. Gerçek GPU/model/metrik yoktur; test kernel’i açıkça SYNTHETIC olarak etiketlenir.
- `.venv/bin/python tests/validate_notebook.py`: Notebook 01 verisiz ve sentetik üç split akışları geçti.
- `.venv/bin/python tests/validate_real_audit_notebook.py`: Notebook 02 sentetik audit/sızıntı akışı geçti; temel 5 PNG, contact sheet/manüel CSV, 8 exact ve 4 near aday korundu.
- `.venv/bin/python tests/validate_wisard_notebook.py`: Notebook 03 bilinen örnek, bilinmeyen ZIP ve eksik ZIP senaryolarında geçti.
- `.venv/bin/python tests/validate_training_notebook.py`: Notebook 04 mevcut sentetik dönüşüm/mocked eğitim/best/test akışı geçti. Bu, yeni gerçek eğitim yapıldığı anlamına gelmez.
- `.venv/bin/python tests/validate_wisard_external_notebook.py`: Notebook 05 tamamlanan sentetik, eksik checkpoint ve bozuk IR senaryolarında geçti.
- `.venv/bin/python -m compileall -q src tests` ve `git diff --check` başarılı. `web/`, Notebook 01–05 ve mevcut inference/matching dosyalarının main ile aynı olduğu ayrıca kontrol edildi.

Yeni testler: yalnızca val JSON/görüntülerinin okunduğunu denetleyen spy; kaynak hash ve önceki DontCare/zero-raw/other-only politikası; varsayılan üç split davranışının korunması; geçersiz split seçimi; kesin IoU bin sınırları; sıfır örtüşmenin GT’ye göre tanımı; duplicate adayları ve paylaşılan native low-conf adayların TP sayılmaması; native xywh/stem ID eşleme ve bilinmeyen ID reddi; 8-bit mean/std/ring kontrast ölçümleri; kaynak-val/native/fixed çıktı üretimi; eksik/bozuk kaynakta model yüklememe; WiSARD piksel/GT ölçümünde target model çağrısı olmaması; experiment matrix’te source-only seçim ve tek-faktör karşılaştırmalar; ek belge talimatlarını yürütmeden CSV/JSON aritmetiği inceleme.

## Ek pakette gerçekten incelenenler

Sağlanan `ThermaSearchAI_Faz06_On_Analiz_Paketi.zip` indirildi ve salt okunur incelendi. SHA256: `c7eae36c1e3ea9c1cf617d85964ae43057af07a1de6744b7de70f1d3c9994f59`. Üç dosyalık paketin 261 satırlık CSV’si, per-frame sayım özdeşlikleri, FN/FP kategori bölümleri, toplam TP/FP/FN ve native aday bucket sayıları JSON özetine karşı programatik kontrol edildi. Kontrol geçti. `review_diagnostic_package` sonucu `outputs/validation/phase06/uploaded_package_review.json` altında Git dışında tutuldu.

Bu, ham tahmin kutularının yeniden doğrulanması değildir: pakette ham predictions.jsonl/native JSON, görüntüler veya checkpoint yoktur. Ek yorumları kullanıcı talimatı olarak uygulanmadı; kullanıcı bu fazda eğitim yapılmamasını ve WiSARD ile seçim yapılmamasını açıkça istedi. Bulguların kapsamı [phase06_evidence_review.md](phase06_evidence_review.md) belgesindedir.

## Görsel/API incelemesi ve sınırlar

Sentetik confidence/FN-candidate histogramı ile kaynak/target display-intensity, contrast ve GT boyut karşılaştırması açılarak incelendi. Grafikler 200 DPI, cohort yoğunluk dağılımları ortak binlerde cohort-fraction olarak çizilir; radyometrik/nedensel açıklama iddiası yoktur. Test çıktıları `outputs/validation/phase06/` altında ve Git dışındadır; kaynak notebook çıktısızdır.

Ultralytics 8.3.228 kaynak wheel’inde validation callback zamanlaması, rectangular dataset pad=.5, native JSON export ve metric denominator yolları incelendi. Bu kaynak incelemesi gerçek CUDA/PyTorch/Ultralytics çıkarım testinin yerine geçmez. Colab Drive OAuth ve gerçek veri üzerinde native/fixed tutarlılığı henüz burada denenmedi. Gerçek girdi yolları dosya sistemiyle kontrol edildi ve bulunmadı; kaynak hata dağılımları Colab çalıştırmasında ölçülecektir.

Public repo ayrı yerel dizine clone/fetch/checkout edilerek sabit `8aae3fb2f8ac964300076b529829ba4331891df7` yardımcı kod revizyonu ve hafif Phase 06 import’u doğrulandı. Bu kontrol paket/model/veri indirmesi veya çıkarım/eğitim çalıştırmadı. Notebook bu revizyona sabitlendikten sonra iki sentetik senaryosu tekrar geçti.

Phase 07 matrisi yalnızca **öneridir**. Gerçek baseline etkin optimizer/lr/augmentasyon ayarları, batch bellek uygunluğu ve kullanıcı eğitim onayı çözülmeden çalıştırılmaz. Validation geçmiş checkpoint seçiminde kullanılmıştır; WiSARD da incelenmiştir. Bağımsız final genelleme için yeni dış veri gerekir. Eski raporlar, checkpoint’ler, kaynak splitler ve frontend değiştirilmedi; eğitim veya veri/model indirmesi yapılmadı.
