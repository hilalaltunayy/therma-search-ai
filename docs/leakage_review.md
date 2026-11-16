# Etiketsiz görüntüler ve sızıntı inceleme sözleşmesi

Kullanıcı PR #2 sonrasında gerçek Colab incelemesinde 2029/290/579 görüntü, 8533/1168/2611 Person, sıfır otomatik kalite sorunu ve sıfır ortak dosya adı bildirdi. Ham nesne anotasyonu olmayan görüntüler 21/3/8, toplam 32 olarak bildirildi. Bunlar kullanıcı tarafından sağlanan bulgulardır; bu geliştirme ortamında yeniden ölçülmedi. Yeni bölüm sonuçları ZIP'ten yeniden üretir; bu sayıları hesaplama çıktısı yerine kullanmaz.

## Seçim ve manuel karar

`images[].filename` ile `annotation[].image_id` ilişkileri incelenir. Bir görüntünün sıfır **ham** anotasyonu varsa `zero_raw_annotations` seçilir. DontCare da bir anotasyondur; DontCare'lı görüntü bu kategoriye girmez. Hatalı/eksik referanslı kutular filtrelenerek boş kalan Sample, sıfır ham anotasyonla eşit sayılmaz. Görüntü kaydı eksik/geçersiz ve ham anotasyonu olduğu hâlde kabul edilen kutusu olmayan dosyalar ayrı inceleme gerekçeleriyle CSV/contact sheet'e eklenir. Bu nedenle bozuk bir kaynakta manuel inceleme satır sayısı 32'den farklı olabilir; sayılar özette ayrı kalır. Eksik görüntü dosyaları hata listesine yazılır; olmayan dosya çizilemez.

`manual_review.csv` şu alanları içerir: review_id, split, filename, ZIP member, seçim nedeni, ham anotasyon sayısı, çözme durumu, human_present, reviewer, review_notes. Son üç alan otomatik doldurulmaz. Kullanıcı human_present için yes/no/uncertain kullanabilir. Sonuçlar kaynak etikete uygulanmaz; negatif örnek kararı otomatik verilmez. Yeni çalıştırma eski karar CSV'sini okumaz veya üzerine yazmaz.

Contact sheet sayfaları split bazında en fazla 20 görüntüdür; tüm seçili mevcut görüntüler kapsanır. Tam göreli dosya adı ve CSV review_id her küçük görselin başlığındadır. 8-bit L görüntüler 0–255 gri ölçeğinde gösterilir. Diğer modlarda Matplotlib görsel ölçeklemesi kullanılır; görseller sıcaklık ölçümü değildir. Bozuk görüntü hücresinde okunamadı mesajı gösterilir; hata özet JSON'a eklenir.

## Eşitlik ile benzerliği ayırma

- `confirmed_identical_file_bytes`: SHA256 dosya baytları eşittir. Metadata/kodlama farkları bu hash'i değiştirebilir.
- `confirmed_identical_decoded_pixels`: dosya baytları farklıdır, ancak doğal görüntü modu, boyutları ve çözülen piksel baytlarının SHA256'sı eşittir. Varsa şeffaflık ve palet bilgisi özete dahildir. EXIF yönlendirmesi ve ton normalizasyonu uygulanmaz.
- Bu iki durum splitler arasında **doğrulanmış tam kopya örtüşmesidir**. Kaynağın neden örtüştüğünü veya tüm uçuş/video sızıntısı kapsamını açıklamaz. Byte/pixel exact grup listeleri aynı çiftleri kapsayabilir; benzersiz çift toplamı `comparison.exact_pairs` alanındadır.
- `review_candidate`: exact eşitlik yoktur; 64 bit dHash Hamming uzaklığı yapılandırılmış eşiğin altındadır veya eşittir. **İnceleme adayıdır; kesin veri sızıntısı değildir.**

DHash, Pillow `convert('L')` ve LANCZOS ile 9×8 küçültmeden sonra her satırdaki sekiz yatay komşu için `sol > sağ` sonucunu bit olarak birleştirir. Eşik varsayılan 4/64, izin verilen aralık 0–64'tür. dHash=0 eşleşmesi piksel eşitliği değildir. 0 veya tüm-1 hash tekdüze/düşük dokulu sahneler için uyarı taşır; diğer hash'lerin yüksek bilgi taşıdığı garanti edilmez. 16-bit termal yoğunluklar L dönüşümünde kaybolabilir. Kırpma, döndürme, ton değişimi ve uçuşun yakın kareleri kaçabilir; farklı hash veya sıfır aday, sızıntı yokluğu kanıtı değildir.

## Kapsam, CPU ve rapor boyutu

Görüntüler ZIP'ten tek tek okunur, CRC kontrolünden geçer, bellekte çözülür. ZIP çıkarılmaz veya yeniden indirilmez. Mevcut güvenli arşiv okuyucusunun yol/üye/boyut kontrolleri kullanılır; bir görüntü en fazla 25 milyon piksel olabilir. Kaynak dosyalar/splitler değiştirilmez. Okunamayan görüntüler SHA/dHash çift karşılaştırmasına dahil edilmez; hesaplanabilen byte hash'leri envanterde ve hatalar özette korunur. Görüntü taraması ve karşılaştırma CPU'da çalışır, yeni bağımlılık yoktur.

Tüm okunabilir **splitler arası** çiftler taranır. Aynı split içindeki tekrarlar bu yeni karşılaştırmanın kapsamı değildir. Yaklaşık 2898 görüntü için split dışı 1.93 milyon çift vardır; bellekte yalnızca dosya envanteri ve sınırlı çıktı çiftleri tutulur. Drive I/O sürebilir.

Near CSV varsayılan en fazla 1000 aday içerir: önce hash'i 0/tüm-1 olmayanlar, sonra küçük Hamming ve deterministik dosya sırası. Exact CSV ilk 5000 çifti içerir; **tüm exact grupların üyeleri** ayrı JSON'da korunur. Toplam sayılar ve her CSV için `*_truncated` JSON'da yer alır. Her iki sınır yapılandırılabilir (en fazla 10000). Sonucun büyük kısmı sınır dışında kalmışsa eşiği ve rapor limitini inceleyin; dosyanın tüm adayları içerdiğini varsaymayın.

En fazla 12 çift PNG kaydedilir; exact ve near kategorileri için ayrı pay ayrılır. Önizlemeler bütün adayların temsili örneklemi değildir. Notebook her kategoriden en fazla ikisini gösterir; kalanlar Drive'dadır. Tüm contact sheet sayfaları notebook'ta gösterilir.

## Dosya adları

Varsayılan regex son `_` veya `-` sonrasındaki sayısal tokenı frame adayı, öncesini grup adayı kabul eder. Bu yalnızca açıkça belirtilmiş bir adlandırma hipotezidir. `filename_group_hypotheses.csv` içinde status daima `unverified_filename_hypothesis` veya `not_inferred` olur. Splitler arasında ortak hipotez grupları özette verilir; gerçek uçuş ID'si sunulmaz. Resmî adlandırma belgesi/uçuş kaydıyla doğrulama ayrı bir araştırma adımıdır.

## Kalıcı çıktı

Notebook 02'de mevcut analizden sonra 9, 10 ve 11. bölümleri çalıştırın. İlk kullanımda güncel notebook'un kurulum ve Drive hücrelerini temiz CPU çalışma zamanında yeniden çalıştırın; eski kernel eski modülleri bellekte tutabilir. Analiz kodu commit'i bootstrap'ta sabitlenir.

Aynı Drive kökünde ayrı, benzersiz `run_leakage_<UTC-zaman>_<kimlik>/` klasörü oluşur. Contact sheet'ler, manual_review.csv, hash_inventory.csv, exact_duplicate_pairs.csv, exact_duplicate_groups.json, near_duplicate_candidates.csv, suspicious_pair PNG'leri, filename_group_hypotheses.csv ve leakage_summary.json üretilir. Özet; sürüm, kaynak arşiv, kod commit'i, zaman, ortam, yapılandırma, hash yöntemleri, kapsam, hata listesi, tüm görsel/kayıt eşleşmeleri ve çıktı SHA256'larını içerir. Önce status=partial yazılır; başarıda complete veya complete_with_errors olur. Complete sızıntı yokluğu veya veri kusursuzluğu anlamına gelmez.
