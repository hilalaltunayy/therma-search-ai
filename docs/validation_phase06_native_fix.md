# Phase 06 native kategori parser düzeltmesi — doğrulama

Native Ultralytics 8.3.228 COCO olmayan tek Person JSON sözleşmesi category_id=1 kullanır. Parser bunu dahili class_id=0'a açıkça eşler. Kurulu sabit sürümün wheel kaynak kodunda `DetectionValidator.init_metrics` ve `save_one_json` incelendi; model çalıştırılmadı.

Sentetik fixture artık gerçek export sözleşmesini temsil eder. Geçersiz kategori kimlikleri (0, 2, -1, boolean, float, string, null), bilinmeyen/yanlış türde görüntü kimlikleri ve belirsiz dosya gövdeleri reddedilir. Geçerli sayısal ve metinsel görüntü gövdeleri, xywh→xyxy dönüşümü, boş export ve manifest tabanlı salt-okunur preflight sınanır. Eski geçici görüntüler olmadan preflight'ın çalıştığı, model yüklemediği ve input hash'lerini koruduğu doğrulanır.

Gerçek Colab checkpoint/veri ve başarısız çalışmanın native JSON dosyası bu ortamda mevcut değildir. Kullanıcının bildirdiği native metrikler yeniden ölçülmedi; önceki raporlara veya sonuçlara müdahale edilmedi. Notebook doğrulamaları sentetik fixture ve model mock'ları kullanır; gerçek performans sonucu değildir. Notebook 04 doğrulaması da yalnız mock eğitimdir.

Çalıştırılan komutlar ve sonuçlar teslim öncesi aşağıya kaydedilir.

- `.venv/bin/python -m unittest discover -s tests -q`: **127 test geçti** (64.344 saniye); Phase 06 alt kümesi 19 testtir.
- `.venv/bin/python tests/validate_notebook.py`: Notebook 01 veri-yok ve sentetik üç split akışı geçti; 12 grafik/görsel.
- `.venv/bin/python tests/validate_real_audit_notebook.py`: Notebook 02 tüm hücreler ve sentetik bütünlük/sızıntı çıktıları geçti.
- `.venv/bin/python tests/validate_wisard_notebook.py`: Notebook 03 tanınan, bilinmeyen ve eksik ZIP yolları geçti.
- `.venv/bin/python tests/validate_training_notebook.py`: Notebook 04 sentetik dönüşüm + mocked train/best/test geçti.
- `.venv/bin/python tests/validate_wisard_external_notebook.py`: Notebook 05 sentetik tam akış, eksik checkpoint ve bozuk IR yolları geçti.
- `.venv/bin/python tests/validate_phase06_notebook.py`: Notebook 06 mevcut native export preflight + sentetik tam akış ve eksik checkpoint yolu geçti; CODE_REF güncellemesinden sonra tekrar geçti.
- `.venv/bin/python -m compileall -q src tests` ve `git diff --check`: geçti.

İlk Notebook 01 denemesinde kernel başlangıç zaman aşımı oluştu; tekrarında her iki akış da geçti. Bazı kernel kapanışlarında ortam kaynaklı Jupyter imza uyarıları çıktı; yukarıdaki başarılı doğrulamaların hücre/çıktı assert'leri ve süreç çıkış kodları kontrol edildi.

Notebook 06 `CODE_REF`, düzeltmeyi içeren **5dfaab3a38d273346887a5ab6ce23f6318484d6e** commit'ine sabitlendi. GitHub'dan ayrı, temiz checkout ile bu commit alınarak category_id=1 → class_id=0 dönüşümü ayrıca sentetik JSON üzerinde doğrulandı. Sabitleme ayrı takip commit'indedir; böylece notebook kendi commit hash'ine döngüsel referans vermez.
