# Phase 06 native kategori parser düzeltmesi — doğrulama

Native Ultralytics 8.3.228 COCO olmayan tek Person JSON sözleşmesi category_id=1 kullanır. Parser bunu dahili class_id=0'a açıkça eşler. Kurulu sabit sürümün wheel kaynak kodunda `DetectionValidator.init_metrics` ve `save_one_json` incelendi; model çalıştırılmadı.

Sentetik fixture artık gerçek export sözleşmesini temsil eder. Geçersiz kategori kimlikleri (0, 2, -1, boolean, float, string, null), bilinmeyen/yanlış türde görüntü kimlikleri ve belirsiz dosya gövdeleri reddedilir. Geçerli sayısal ve metinsel görüntü gövdeleri, xywh→xyxy dönüşümü, boş export ve manifest tabanlı salt-okunur preflight sınanır. Eski geçici görüntüler olmadan preflight'ın çalıştığı, model yüklemediği ve input hash'lerini koruduğu doğrulanır.

Gerçek Colab checkpoint/veri ve başarısız çalışmanın native JSON dosyası bu ortamda mevcut değildir. Kullanıcının bildirdiği native metrikler yeniden ölçülmedi; önceki raporlara veya sonuçlara müdahale edilmedi. Notebook doğrulamaları sentetik fixture ve model mock'ları kullanır; gerçek performans sonucu değildir. Notebook 04 doğrulaması da yalnız mock eğitimdir.

Çalıştırılan komutlar ve sonuçlar teslim öncesi aşağıya kaydedilir.
