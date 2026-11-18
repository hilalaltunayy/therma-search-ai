# WiSARD tek çalıştırma doğrulama kaydı

Tarih: 2026-11-18. Bu kayıt gerçek veri seti analizi veya model deneyi değildir.

## Gerçekten çalıştırılan kontroller

- `.venv/bin/python -m unittest discover -s tests -q`: **74 test geçti**; önceki 59 test ve 15 yeni sentetik test. Klasör/son kare adaptörü, bilinmeyen yapıda şema kapısı, bağımsız sayımlar, count.txt dışlama/kıyaslama, piksel dönüşümü/küçük nesne paydası, iki eşleştirme hipotezi, bildirilen 1–264 / 0–263 numara aralıklarında 263/264 aday, yinelenen anahtarın dışlanması, bozuk görüntü/eksik/boş/geçersiz etiket ayrımı, bilinmeyen sınıflar, sınır dışı kutular, modalite içi SHA/dHash, zamansal farklar, EXIF zaman adayları ve kesinlik sınırları, orphan/missing/mismatch count.txt kalite bulguları, çıktı dosyaları ve önceki run’ın korunması sınandı.
- `.venv/bin/python tests/validate_wisard_notebook.py`: Notebook 03 nbformat şeması ve bütün hücreleri üç ayrı kernel’de geçti: **bilinen sentetik örnek**, **bilinmeyen sentetik ZIP**, **eksik ZIP**. Gerçek bilinen klasör adlarını kullanan fixture yalnızca 24 yapay küçük görüntüdür; 18’er anotasyon gerçek WiSARD sonucu değildir. A için 11, B için 12 aday; her hipotez için 10 PNG ve gerekli JSON/CSV/Markdown çıktıları doğrulandı. Bilinmeyen yapıda etiket/eşleştirme varsayılmadı; eksik ZIP’te tanılama üretildi.
- `.venv/bin/python tests/validate_notebook.py`: Notebook 01 veri bulunmayan ve sentetik üç split modlarında geçti, 12 görsel çıktı. Notebook 01 değişmedi.
- `.venv/bin/python tests/validate_real_audit_notebook.py`: Notebook 02 mevcut sentetik arşiv denetimi ve sızıntı akışı geçti; temel 5 PNG, contact sheet/manüel CSV, 8 exact ve 4 near aday korundu. Notebook 02 değişmedi.
- `.venv/bin/python -m compileall -q src tests` ve `git diff --check` başarılı.
- Sentetik çift ground-truth PNG’si, boş anotasyon contact sheet’i ve kutu boyut histogramı dosyadan açılıp görsel incelendi. Başlık/eksenler ve kırmızı kutular okunabilir. Şekiller 200 DPI; farklı modaliteler kendi piksel uzayında gösterilir.

Test çıktıları `outputs/validation/wisard_one_pass/` altındadır, Git’e eklenmez. Kaynak notebook boş çıktı/çalıştırma sayaçlarıyla teslim edilir. HIT-UAV kodu, mevcut veriler ve eski raporlar değiştirilmez. Bağımlılık eklenmedi; testler için requirements.txt aralıklarına uygun yerel .venv kullanıldı.

## Kapsam sınırları

Gerçek 1.018.780.195 baytlık Drive ZIP’i bu ortamda mevcut değildir. Kullanıcının 528 görüntü, 1006/1022 anotasyon, üçer boş etiket ve 263/264 eşleme adayı referansları bu geliştirme çalışmasının gerçek veri ölçümü olarak sunulmaz. Kullanıcı referansları yeni notebook’ta bağımsız yeniden hesaplanır. Colab Drive OAuth ve gerçek sensör görüntülerindeki görsel semantik ayrıca denenmedi.

EXIF/metadata adayları kaydedilir ve bilinen EXIF çekim zamanı alanları iki hipotezde karşılaştırılır; resmî eşleme belgesi veya ortak kamera saati/gecikmesi doğrulanmadı. `synchronization_confirmed=false`; seçilen aday yalnızca sayım/kapsam temelli geçici hipotezdir. Lisans/sürüm/yayıncı checksum’ı bağımsız doğrulanmadı. Eğitim, tam arşiv indirmesi, etiket değişikliği veya rastgele split yapılmadı.
