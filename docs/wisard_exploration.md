# WiSARD · Notebook 03 tek çalıştırma akışı

Notebook 03 artık kullanıcı tarafından gerçek ZIP’te doğrulanan MtErie multi-modal örneği için otomatik adaptör kullanır. Genel `WisardArchive`, `PairingSpec`, `LabelSpec` ve `run_wisard_exploration` API’lerinin güvenli, varsayılan kapalı davranışı korunur; başka veri setleri için otomatik YOLO veya sensör tahmini yapılmaz.

## Colab kullanımı

1. PR merge edildikten sonra [Notebook 03’ü Colab’da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/03_wisard_exploration.ipynb).
2. CPU çalışma zamanı ile **Çalışma zamanı → Tümünü çalıştır** seçin. İlk Drive bağlantısında Google erişim izni gerekebilir; hücre düzenlemek gerekmez.
3. Önceden yüklediğiniz `/content/drive/MyDrive/ThermaSearchAI/datasets/WiSARD_Multi_Modal_Sample.zip` okunur. Çıktılar otomatik olarak `ThermaSearchAI/reports/wisard/run_wisard_<UTC>_<benzersiz>/` altına yazılır. Her çalıştırma yeni dizin açar; önceki raporlar korunur.

Public kod bootstrap’ı doğrulanmış yardımcı kod commit’ine sabitlenir; kullanılan gerçek HEAD özet JSON’una yazılır. Yalnızca mevcut Pillow/Matplotlib sürüm aralıkları kontrol edilir; notebook kernel paketleri değiştirilmez. ZIP indirilmez/çıkarılmaz. Arşiv yoksa açık hata/tanılama raporu üretilir; sıfır görüntü ölçülmüş gibi gösterilmez.

## Otomatik şema

- `210417_MtErie_Enterprise_IR_0004/` ve `210417_MtErie_Enterprise_VIS_0003/` altında, dosya gövdesinin sonunda sekiz basamaklı kare numarası bulunan görüntüler; iki klasör aynı kökün altında olmalıdır. Modalite kanal sayısından çıkarılmaz. Görüntüye karşılık gelen aynı gövdeli `.txt` okunur.
- `count.txt` anotasyon dosyası değildir; dosya içindeki toplam insan/görüntü sayıları bağımsız yeniden hesaplanan değerlerle karşılaştırılır.
- Beş sütunlu normalize YOLO (`class_id cx cy width height`). Sınıf 0=Person, **kullanıcının gerçek etiket/görsel incelemesine** dayanır. [Makale](https://doi.org/10.1109/IROS47612.2022.9981298) ve [resmî sayfa](https://sites.google.com/uw.edu/wisard/) insan arama-kurtarma bağlamını belgeler; sayısal ID sözlüğü bu ortamda bağımsız doğrulanmış değildir. `class_semantics.json` ve ground-truth kutulu görseller bu ayrımı korur.
- Tüm ID’ler ham satır ve ayrıştırılmış kutu olarak ayrı sayılır. Bilinmeyen ID insan olarak eşlenmez. Geçersiz satırlar, sınır dışı kutular, eksik/boş/okunamayan etiketler, orphan TXT ve yinelenen kare anahtarları raporlanır. Kutular kırpılmaz.
- Bilinmeyen görüntü yolu veya birden fazla kök varsa otomatik etiket/eşleştirme kapatılır. Envanter, görüntü özellikleri, metadata adayları ve tanılama raporu yine üretilir. Kullanıcıdan regex girip devam etmesi istenmez; yeni yapıya uygun adaptör gerekir.

Kullanıcının önceki gerçek ölçümü: ZIP 1.018.780.195 bayt; modalite başına 264 görüntü, IR 1006 / VIS 1022 insan anotasyonu, üçer boş TXT, eksik TXT/geçersiz satır yok. Örnek çözünürlükleri IR 640×512 / VIS 3840×2160. Bunlar `USER_REFERENCE` olarak ayrı saklanır; yeni sonuçlara kopyalanmaz. Görüntülerin tamamı yeniden çözülür. **Anotasyon sayısı benzersiz kişi sayısı değildir; IR/VIS birleştirilerek benzersiz insan sayısı üretilmez.**

## Eşleştirme kanıtı ve sınırlar

A: IR n ↔ VIS n; B: IR n ↔ VIS n−1. Bildirilen aralıklarda A 263, B 264 adaydır; kod tüm kare numaralarından kapsamı yeniden hesaplar. Yinelenen anahtarlarda ilk dosya seçilmez. Kapsam paydası bütün modalite görüntüleridir. Sayım karşılaştırmaları yalnızca sorunsuz etiketli karelerde yapılır; eksik etikete sıfır atanmaz.

Her hipotez için işaretli/mutlak farkın ortalaması, medyanı, aralığı, dağılımı, eşit sayım oranı ve korelasyonu kaydedilir. Ardışık insan sayısı değişimi karşılaştırmaları yalnızca iki akışta da tam bir kare ilerleyen adayları kapsar. Sabit veya üçten kısa seride korelasyon tanımsızdır (`null`). Geçici tercih düşük sayım MAE’si, eşitse yüksek kapsam ile seçilir; tam eşitlikte tercih yoktur. Bu sıra bir **sayım uyumu sezgisidir**; yanlış eşleştirmeyi de tercih edebilir. Eğitim/füzyon için kesin eşleme sayılmaz.

Yeterli okunabilir aday varsa her hipotezin tüm zaman aralığına yayılan 10 farklı çifti, her görüntünün kendi piksel uzayında kırmızı ground-truth kutularıyla kaydedilir. Kutular model çıktısı değildir. Eşleşmeyen sınır kareleri ayrıca, kesin eş değilmiş gibi açık başlıkla gösterilir. Görsel seçimler manifestte saklanır.

EXIF DateTimeOriginal ve varsa alt saniyeler her iki hipotezde karşılaştırılır; zaman farkı dağılımı kaydedilir. ZIP tarihleri çekim zamanı sayılmaz. Ortak saat/gecikme ve yayıncı eşleme şeması doğrulanmadıkça EXIF eşitliği bile kesin senkronizasyon kanıtı kabul edilmez. Bütün metin/JSON/CSV/XML metadata adayları envantere alınır ve 64 KiB’ye kadar önizlenir; kesilme açıkça belirtilir. Bilinmeyen sidecar şemasından resmî eşleme uydurulmaz. `synchronization_confirmed` bu akışta `false` kalır.

## Bütünlük ve sızıntı incelemesi

2 GiB sıkıştırılmış ZIP, 8 GiB toplam açılmış veri, 32 MiB üye ve 25 milyon piksel sınırları korunur. Yol traversal/symlink/yinelenen arşiv üyeleri reddedilir. Görüntüler gerçekten yüklenir; okunan üyelerde ZIP CRC kontrol edilir. Dosya/mod/piksel SHA256 ve 64-bit yatay dHash hesaplanır. Modalite içindeki tüm okunabilir çiftler Hamming≤4 yakınlık ve byte/piksel eşitliği için taranır; CSV sonuçları kesilmez. Düşük bilgi hash uyarıları korunur. Bunlar aynı uçuşu tanımlamaz veya sızıntı yokluğunu kanıtlamaz.

Ardışık karelerin dHash farkı ve **modalite içindeki** insan merkezi medyanının değişimi raporlanır. Merkez değişimi nesne kimliği/takip değildir; kamera hareketi, örtülme ve giriş/çıkışlardan etkilenir. Modaliteler arası kutu koordinatı karşılaştırması veya geometrik hizalama yapılmaz.

Boş etiketli görüntülerin tamamı listelenir ve contact sheet’e kaydedilir; otomatik negatif sayılmaz. Boyut istatistikleri yalnızca okunabilir görüntülerdeki sınırlar içi Person kutularını kapsar. Küçük nesne eşikleri: alan<32² piksel², genişlik<16, yükseklik<16, her iki kenar<16 piksel. Her oran kendi modalite paydasını içerir. Çözünürlük/perspektif farkı nedeniyle piksel ölçekleri fiziksel nesne boyutu gibi karşılaştırılmamalıdır.

Tek uçuş kapsamı kaynak/kullanıcı beyanıdır. Yakın kareler ve modalite eşleri bağımsız örnek sayılmaz. Rastgele train/val/test ayrımı yapılmaz; yeni uçuş kimliği oluşturulmaz; eğitim başlamaz. YOLO11s hazırlığı için bağımsız uçuş grupları, etiket/boş görüntü incelemesi ve değerlendirme protokolü gerekir. Son bilimsel karar kullanıcıya aittir.

## Otomatik çıktılar

İstenen `wisard_summary.json`, `image_metadata.csv`, `annotation_statistics.csv`, `pairing_hypotheses.csv`, `pairing_evidence.json`, `data_quality.json`, `hit_uav_comparison.csv`, 200 DPI PNG’ler ve on bölümlü `wisard_analysis_report.md` yazılır. Ek olarak tam envanter, piksel kutuları CSV’si, boş etiket listesi, EXIF/metadata adayları, sahne benzerlik çiftleri, temporal değişimler, sınıf anlamı ve görsel seçim manifesti kaydedilir. Özet çıktı dosyalarının SHA256 değerlerini içerir. HIT-UAV karşılaştırması önceki kaynak/kullanıcı bilgilerini kullanır; HIT-UAV yeniden okunmaz.

Kod: `src/data/wisard_sample.py` (hesaplar), `wisard_sample_reports.py` (çıktılar); mevcut `wisard_reports.run_wisard_sample_analysis` tek çağrı giriş noktasıdır. Gerçek ZIP bu geliştirme ortamında yoktur; sentetik fixture testleri gerçek sayımların veya fiziksel eşleştirmenin doğrulaması değildir.
