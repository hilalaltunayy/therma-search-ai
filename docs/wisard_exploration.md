# WiSARD keşif sözleşmesi

## Kaynak ve kanıt düzeyleri

Resmî sayfa: https://sites.google.com/uw.edu/wisard/ . Makale: *WiSARD: A Labeled Visual and Thermal Image Dataset for Wilderness Search and Rescue*, IROS 2022, DOI https://doi.org/10.1109/IROS47612.2022.9981298 . Kullanıcı resmî sayfanın Visual Only 26.862, Thermal Only 29.989 etiketli görüntü ve bu alt kümelerin içinden 15.453 eşzamanlı çift bildirdiğini doğruladı. Bunlar yerel ölçüm değildir ve çiftler bağımsız bir üçüncü görüntü toplamı olarak eklenmez.

Tam arşiv yaklaşık 40,54 GB; multi-modal örnek yaklaşık 971,6 MB ve tek veri toplama uçuşudur (resmî sayfa beyanı, kullanıcıdan). Dağıtım sürümü/örnek dosya ID'si, gerçek klasörler, boyutlar, etiket ve eşleştirme şeması bu ortamda doğrulanmadı. 2026-11-16 resmî sayfa isteği ortam politikasından 403 aldı. Veri lisansı metni ve kapsamı hâlâ doğrulanmalı; lisans adı uydurulmadı. GitHub kod lisansı veya açık indirme bağlantısı veri lisansı yerine geçmez. LICENSE/COPYING/NOTICE/README adayları bulunursa sınırlı metin önizlemesi kaydedilir, kullanım koşulları otomatik kabul edilmez.

## İndirme ve depolama

Notebook 03 hiçbir veri seti indirmez. Örnek indirmesi de önce kullanıcı onayı gerektirir; bu teslimde indirme işlevi yoktur. Kullanıcı önceden sağladığı örneğin mevcut gerçek yolunu seçer. Adında WiSARD geçen mevcut ZIP'ler proje veri dizininde listelenebilir; tek uygun boyutlu aday seçilebilir. Birden fazla aday otomatik seçilmez. Bu ad/uygun boyut kontrolü kaynağın veya sürümün doğrulanması değildir.

2 GiB üzerindeki sıkıştırılmış ZIP reddedilir; böylece tam 40,54 GB arşiv bu iş akışında açılmaz. Toplam açılmış boyut 8 GiB, tek üye 32 MiB, görüntü 25 milyon piksel ile sınırlıdır. Yol traversal, symlink ve yinelenen üye yolları mevcut güvenli ZIP yardımcılarıyla denetlenir. ZIP çıkarılmaz; kaynak dosyalar değiştirilmez. Tam arşiv checksum'ı bu analizde yeniden hesaplanmaz. Kısmi metin önizlemesi CRC/tam dosya bütünlüğü kontrolü değildir; sınırlama rapora yazılır.

Varsayılan kalıcı kök: `/content/drive/MyDrive/ThermaSearchAI/reports/wisard/`. Her çalıştırma yeni `run_wisard_.../` klasörüdür. Arşiv yokken kaynak/plan JSON, HIT-UAV karşılaştırma CSV ve özet üretilir; yerel görüntü sayısı None kalır. Arşiv varsa envanter CSV, gerçek boyut/mod/kanal CSV, ham etiket/lisans önizlemeleri, path context ipuçları, eşleştirme/anotasyon raporları eklenir. Sonuçlarda arşiv yolu/boyutu, kod commit'i, tarih, yapılandırma, ortam ve çıktı SHA256'ları saklanır. Önceki raporlara dokunulmaz.

## Doğrulama kapıları

İlk çalıştırma `PairingSpec()` ve `LabelSpec()` ile yapılır. Metadata veya split belgesi otomatik önizlemeye girmiyorsa gerçek üye yolunu envanterden alıp `EXTRA_PREVIEW_MEMBERS` listesine ekleyin (en fazla 12); yeni run içinde sınırlı metin önizlemesi kaydedilir, üyelik şeması otomatik yorumlanmaz. Kural durumu `not_configured` kalır; sahte eş/Person kutusu veya sıfır sınıf metriği üretilmez. Görüntü modundaki RGB/tek kanal bilgisi sensör modalitesini kanıtlamaz; sahte renkli termal de RGB olabilir. Etiket adayı TXT/JSON/XML/CSV bir split listesi veya doküman da olabilir. Dosya formatı yalnızca uzantıyla onaylanmaz.

Eşleştirmede gerçek dosyalar/kaynak belgesi incelendikten sonra iki tam yol regex'i ve `key` grubu, kanıt notu ve confirmed=True gerekir. Anahtar global olarak tek olmalıdır; çakışmada ilk dosya seçilmez. RGB ve termal regex'i aynı üyeyi yakalarsa belirsiz olarak raporlanır. Aynı anahtarlı dosyalar fiziksel senkronizasyon/geometrik hizalama kanıtı değildir. İsteğe bağlı flight/split grupları path token hipotezidir; gerçek uçuş kimliği değildir. Örtüşen tokenlar aday risk olarak gösterilir.

Etiketlerde yalnızca açıkça doğrulanmış `yolo_cxcywh_normalized` adaptörü desteklenir: beş sütun `class cx cy w h`, normalize merkez ve boyutlar. Bu **WiSARD'ın gerçek şemasının doğrulandığı iddiası değildir**; kullanıcı gerçek arşivde bu biçimi görürse kullanılabilir. Sınıf sözlüğü, Person IDleri, image_regex, label_template ve kaynak kanıtı gerekir. Piksel xyxy dönüşümü görüntünün gerçek çözünürlüğünü kullanır. Bilinmeyen sınıf, NaN, geçersiz alan veya beşten farklı sütun raporlanır. Polygon, OBB, JSON/XML veya piksel koordinatları sessizce bu adaptöre sokulmaz; ayrı doğrulanmış adaptör gerekir. Sınır dışı kutular kırpılmaz. Eksik/boş etiket negatif örnek kararı değildir. Aynı etiketi RGB/termal iki görüntüye eşleyip çift saymak hata olarak gösterilir.

## Bilimsel plan ve sızıntı

Tek uçuş örneği bağımsız uçuşlar arası genellemeyi ölçmez ve tam veri setini temsil ettiği varsayılmaz. Aynı uçuşun yakın kareleri ve eşzamanlı RGB/termal eşler rastgele train/test'e dağıtılırsa değerlendirme iyimserleşebilir. Mevcut metadata ve üyelik listeleri incelenmeli, resmî adlandırma/senkronizasyon bilgisi doğrulanmalıdır. Yol adı veya kanal sayısı bu kanıtın yerine geçmez. Notebook yeni split, etiket veya eğitim üretmez; son karar kullanıcıya aittir. Yakın kare hash/sızıntı taraması burada uygulanmış sayılmaz; riskin açık kalması raporlanır.

HIT-UAV karşılaştırması kullanıcı tarafından doğrulanan 2898 görüntü/640x512/piksel bbox ve özgün splitleri, WiSARD kaynak beyanı ile yerel örnek ölçümünü ayırır. Sensör/perspektif, sınıf semantiği, farklı çözünürlük ve eşleştirme/hizalama farkları ele alınmadan veri setleri birleştirilmez veya model başarımı karşılaştırılmaz.

## Çalıştırma

Notebook 03'ü temiz Colab CPU çalışma zamanında açın. Aşama 1 kaynağı/planı okuyun; kurulum public kodu sabit commit'ten alır ve `requirements-colab.txt`yi `--no-deps` ile kullanır. Drive bağlantısını açın, varsa gerçek SAMPLE_ZIP_PATH seçin. ZIP yoksa source_only raporu oluşur. İlk ZIP çalıştırmasında kuralları kapalı tutun; envanteri/önizlemeleri inceleyip doğruladığınız kuralları doldurun ve kural hücresinden itibaren yeniden çalıştırın. En fazla 3 çift ve 3 Person kutulu örnek kaydedilir; tüm görüntüler Drive'a tekrar yazılmaz. CONNECT_DRIVE=False yalnızca yerel rapor üretir; Colab kapanınca kaybolabilir ve Drive'a kaydedilmiş sayılmaz.
