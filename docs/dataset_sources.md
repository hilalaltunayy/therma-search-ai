# Veri kaynakları ve doğrulama kaydı

Kontrol tarihi: **2026-11-13**. Bu belge kaynak beyanını, hedef sürümü ve gerçekten yapılan ölçümü ayırır. Hiçbir veri seti veya model ağırlığı indirilmedi.

## HIT-UAV

- Resmî depo: https://github.com/suojiashun/HIT-UAV-Infrared-Thermal-Dataset
- Okunan README'nin sabit referansı: https://github.com/suojiashun/HIT-UAV-Infrared-Thermal-Dataset/blob/c5ce70a049d38036fe767b68692c3411ef04e900/README.md
- Makale: Suo ve diğerleri, *HIT-UAV: A high-altitude infrared thermal dataset for Unmanned Aerial Vehicle-based object detection*, Scientific Data 10, 227 (2023). DOI: https://doi.org/10.1038/s41597-023-02066-6
- Kullanıcının belirlediği esas dağıtım: **resmî Zenodo v1.2.1**. Arama: https://zenodo.org/search?q=HIT-UAV

**Gerçekten doğrulanan:** Resmî GitHub README erişildi. README standart merkez tabanlı `[xc,yc,w,h]` ve döndürülmüş `[xc,yc,w,h,theta]` kutuları; `normal_xml`, `normal_json`, `rotate_xml`, `rotate_json` gösterimlerini belgeliyor. README, Person/Bicycle/Car/OtherVehicle adlarını veriyor. Buradaki klasör adları yalnızca README beyanıdır; indirilecek v1.2.1 ağacı ölçülmedi. DontCare varlığı, yazımı, sıklığı ve semantiği gerçek etiketlerden ayrıca doğrulanacak.

**Doğrulanamayan:** Zenodo API isteği ortamın proxy politikası nedeniyle `403 Forbidden` ile engellendi. Sabit v1.2.1 kayıt ID'si, lisans, checksum, arşiv türü/adı/boyutu ve gerçek şema bu oturumda doğrulanamadı. README'nin sayısal beyanları yerel veri ölçümü olarak kullanılmadı. GitHub deposu klonlanmadı; gerçek görüntü ve etiketlerin klonla geldiği varsayılmadı.

### Colab'da kaynak doğrulama sırası

1. Makale/resmî depo üzerinden Zenodo kaydına gidin; **v1.2.1 sürüm kaydını** seçin. Başlık, yazarlar ve DOI ilişkisini kontrol edin. Sürüm kaydının sayısal ID'sini notebook'a girin; concept DOI/latest yönlendirmesini sabitleme yerine kullanmayın.
2. Metadata hücresini açın. Kod sabit ID, HIT-UAV başlığı, sürüm, lisans alanı ve dosyaların varlığını denetler. Kaynak JSON'u `outputs/` içinde saklanır. Hata veya farklı sürümde durur.
3. Lisansın tam metnini ve atıf/yeniden dağıtım koşullarını okuyup tarihli kaynak notuna yazın. Lisans alanının dolu olması, kullanım koşullarını kabul etmiş olduğunuz anlamına gelmez. Kaynaklar çelişiyorsa bunu çözmeden veriyi paylaşmayın.
4. İndirmeye kullanıcı karar verdiğinde tek dosya seçin; boyut/disk sınırlarını belirleyin. Yayıncı checksum ve dosya boyutunu kontrol edin. Kaynak URL, sürüm, lisans, zaman ve yerel SHA256 manifestte saklanır. MD5 bozulma denetimidir, güvenilir kaynak yerine geçmez.
5. ZIP ise üyeleri inceleyip ayrı onayla yeni dizine açın. Diğer arşiv türlerinde doğrulanmış açıcı eklenmeden devam etmeyin.
6. Yerel dosya ağacı ve ham etiket örnekleriyle adaptörü seçin. Esas splitleri değiştirmeyin. DontCare ve koordinat kararlarını kullanıcıya sunun.

## WiSARD

- Proje sayfası: https://sites.google.com/uw.edu/wisard/
- Yazar Christopher R. Hayner'ın yayın kaydı, proje sayfasını doğrulayan birincil bağlantı: https://github.com/haynec/haynec.github.io/blob/1cae3376c5e51fe61a378d89ed4e2c6d9afbf978/papers/wisard.md
- Broyles, Hayner ve Leung, *WiSARD: A Labeled Visual and Thermal Image Dataset for Wilderness Search and Rescue*, IROS 2022, 9467–9474. DOI (yazarın yayın kaydından): https://doi.org/10.1109/IROS47612.2022.9981298

**Gerçekten doğrulanan:** Yazarın yayın kaydı okundu; başlık, yazarlar, yayın künyesi ve resmî proje sayfası bağlantısı doğrulandı.

**Doğrulanamayan:** Proje sitesine bu ortamdan erişim `403` verdi. Dağıtım sürümü, lisansın veri kapsamı, tam/örnek arşiv bağlantıları, boyutları, checksum değerleri, klasör/etiket yapısı doğrulanamadı. Üçüncü taraf depolardaki lisans ve sayılar birincil doğrulama olarak kabul edilmedi. Kullanıcının belirttiği 40 GB üzerindeki tam arşiv için indirme kodu eklenmedi.

### Küçük örnek arşiv seçeneği

İlk WiSARD çalışması için resmî sayfadaki **küçük örnek arşivi** tercih edin. Önce sürüm veya değişmez dosya ID'si, yayımlanma tarihi, lisans ve boyutu kaydedin. Örnek arşiv bağlantısı doğrulanmadan gdown/Drive ID tahmini yapmayın. Tam arşivle otomatik değiştirme yapılmaz.

Örneği kullanıcı kendi Colab/Drive alanına sağladıktan ve yayıncı checksum'ını doğruladıktan sonra aşağıdaki salt okunur araç kullanılabilir (bu bir WiSARD şema adaptörü değildir):

```python
from pathlib import Path
from src.data.inventory import inventory, preview_label
from src.data.audit import file_digest
sample_root = Path('/content/drive/MyDrive/THERMA/wisard_sample')  # Kendi yolunuz
info = inventory(sample_root)
print(info['extensions'])
print(info['directories'][:30])
print(info['label_candidates'][:20])
# Sonraki adım: gerçek bir etiket adayı seçip preview_label ile inceleyin.
# Dosya SHA256: file_digest(Path('kendi_arşiv_yolunuz'))
```

Yayıncı checksum yayımlamıyorsa bunu açık yazın. Yerel SHA256 sonradan aynı dosyayı tanımlar; indirme sırasında yayıncıdan eksiksiz geldiğini bağımsız olarak kanıtlamaz. Küçük örnekten tam dağılım veya performans genellemesi yapılmaz. RGB/termal eşler ve aynı uçuş/konum grupları gelecekteki split sızıntısı denetiminde birlikte ele alınır.
