# Faz 06 — Sağlanan ön analiz paketinin incelemesi

İncelenen ek: `ThermaSearchAI_Faz06_On_Analiz_Paketi.zip`, SHA256 **c7eae36c1e3ea9c1cf617d85964ae43057af07a1de6744b7de70f1d3c9994f59**. Ek belgelerdeki öneriler görev talimatı sayılmamıştır; bu sohbetin kullanıcı isteği kapsamı belirler. Yeni eğitim veya gerçek model çıkarımı yapılmamıştır.

Paket üç dosya içerir: `Faz06_WiSARD_Hata_Analizi.md`, `hata_analizi_ozet.json`, `kare_bazli_hata_siniflari.csv`. **Ham predictions.jsonl, native predictions.json, görüntüler ve checkpoint pakette yoktur.** Özetin referans verdiği orijinal değerlendirme ZIP SHA256’sı `6b9cb9659709ea2a721c08d02668258008ea8897a5dee6815bc0e9a5671b505c` olup bu ekteki ZIP’in hash’i değildir; orijinal değerlendirme arşivi burada incelenmemiştir.

## Doğrudan kontrol edilen kanıt

CSV 261 eşsiz kare içeriyor. Her satırda `TP+FN=GT` ve `TP+FP=detections`; FN/FP IoU kategori bölümlerinin satır ve toplam sayıları tutarlı. CSV toplamları JSON özetiyle uyuşuyor:

| Sayım | Toplam |
|---|---:|
| GT | 1006 |
| Fixed tahmin | 739 |
| TP / FP / FN | 207 / 532 / 799 |
| FN sıfır örtüşme | 591 |
| FN en iyi IoU [0.30,0.50) | 147 |
| FP en iyi GT IoU [0.30,0.50) | 235 |
| FP IoU≥.50 | 22 |
| Native en iyi IoU≥.50, score [.001,.01) / [.01,.10) / [.10,.25) | 218 / 140 / 52 |
| Native en iyi IoU≥.50, score≥.25 | 1 |

218+140+52=410 aday GT’dir. Bu aritmetik doğrulama **ham kutu geometrisinin veya birleştirilmiş native/fixed eşleşmenin yeniden doğrulanması değildir**. Kullanıcının doğruladığı mAP50=.1453 ve mAP50:95=.0415, paketin özetiyle uyumludur; ham native metrik dizileri bu ekte yoktur. Bunlar yeni model ölçümü olarak sunulmaz.

## Olası açıklamalar ile kanıtı ayırma

591/799 sıfır örtüşme, ilgili eşleşmeyen GT ile fixed tahminler arasında örtüşme bulunmamasıdır. Görüntünün tamamında tahmin olmadığı anlamına gelmez. Düşük güven, hiç öneri üretilmemesi, büyük lokalizasyon hatası ve sahne karışması aynı gözlemle uyumlu olabilir; bu özetten neden ayrıştırılamaz.

147 FN ve 235 FP’nin [.30,.50) bandında bulunması lokalizasyon/etiket geometrisi incelemesini gerekçelendirir; her FP’nin sahnede uydurma bir insan olduğu söylenemez. IoU≥.50 FP’ler yinelenen/eşleme çakışması **adayıdır**, fiziksel nesne kimliği kanıtı değildir. Küçük kutularda birkaç piksel kayma büyük IoU değişimi yaratabilir.

410 düşük güvenli native örtüşme adayı, ayrı prosedürdeki en yüksek IoU’lu önerilerden hesaplanmıştır. Bir öneri birden fazla GT ile örtüşebilir; native preprocessing, NMS ve score tabanı da fixed geçişten farklı olabilir. **Kurtarılabilir TP, net eşik düşürme kazancı veya WiSARD üzerinde threshold seçme gerekçesi değildir.** Paket kare 245 için bir yüksek güvenli native aday bildiriyor; ham çıktılar olmadan bug veya belirli preprocessing nedeni doğrulanamaz.

Paket GT medyanını yaklaşık 13.00×22.76 piksel; width<16 recall’unu 130/659, height<16 7/70 ve both<16 4/50 olarak bildiriyor. Boyut/alt grup oranları özet bağlamıdır; ham GT listesi bu ekte bulunmadığı için bu değerler burada yeniden hesaplanmadı. Gruplar örtüşür. Ek raporun CPU kullanımı gözlemi tek başına düşük skorun sebebi değildir.

## Geliştirme sınırı

WiSARD artık incelenmiş diagnostic development verisidir. Kaynak-validation hata analizi gerçek veriler Colab’da mevcutken Notebook 06 ile yapılır. Confidence, eğitim hiperparametreleri ve checkpoint seçimi yalnızca HIT-UAV train/validation içinde kalır; WiSARD veya HIT-UAV test seçim için kullanılmaz. Nihai genelleme için farklı görev/uçuş/sahalardan yeni, seçim sırasında kapalı tutulmuş dış veri ve doğrulanmış negatif sahneler gereklidir.
