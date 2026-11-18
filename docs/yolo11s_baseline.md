# HIT-UAV YOLO11s exploratory baseline

Bu teslim eğitim/değerlendirme altyapısıdır; gerçek Drive verisi veya GPU eğitimi geliştirme ortamında çalıştırılmamıştır. Örnek sentetik metrikler gerçek model başarımı değildir.

## Colab’da ilk çalışma

1. PR merge edildikten sonra [Notebook 04](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/04_hit_uav_yolo_training.ipynb) dosyasını açın.
2. **Çalışma zamanı → Çalışma zamanı türünü değiştir → GPU** seçin. **Tümünü çalıştır** deyin; ilk Drive erişimini Google üzerinden yetkilendirin. Hücre/şema/regex girmeniz gerekmez.
3. Mevcut `/content/drive/MyDrive/ThermaSearchAI/datasets/hit_uav_v1.2.1.zip` okunur. Veri indirilmez. Dönüşüm denetlenmeden pretrained model yüklenmez/eğitim başlamaz. Eğitim için resmi `yolo11s.pt` ağırlığı gerektiğinde Ultralytics tarafından indirilir.
4. Gerçek eğitim GPU’da çalışır; validation ile seçilen `best.pt` ayrı testten geçirilir. CPU fallback yoktur. İlk ayarlar 40 epoch, batch 8, patience 10, imgsz 640, seed 42, pretrained=True, task=detect. Toplam GPU belleği 6 GiB altındaysa batch en fazla 4 olur; istenen/efektif değer ve gerekçe kaydedilir.
5. Kalıcı sonuçlar `ThermaSearchAI/runs/hit_uav_yolo11s/run_yolo11s_<UTC>_<id>/` altındadır. Çalışma dizini eğitim başında yazdırılır. Her çalıştırma yeni dizin açar; otomatik resume/önceki run’ın üzerine yazma yoktur.

GPU yoksa notebook açık uyarıyla durur. OOM/bağlantı kesintisi durumunda otomatik ayar değişimi veya CPU eğitimi yapılmaz. İlgili run’ın best/last ağırlıkları, results.csv ve hata kaydı eldeki durumu korur; başarılı test sonucu varmış gibi işaretlenmez. Farklı batch ile yeni deney yapılırsa yeni run oluşturun, test sonuçlarına göre ayar seçmeyin. Colab’ın oturum süresi 40 epoch’u tamamlamayı garanti etmez.

`requirements-training-colab.txt` yalnızca bu notebook içindir; Ultralytics 8.3.228 sabittir. Colab’ın mevcut CUDA torch/torchvision kurulumu kullanılır, zorla yeniden kurulmaz. Bu bağımlılıkların gerçek sürümleri, GPU/CUDA/cuDNN ve Python sürümü raporlanır. Mevcut keşif notebook’larının requirements dosyaları değişmez. AMP=False (FP32) seçilmiştir; otomatik AMP kontrolünün ek model indirmesi önlenir. `deterministic=True` ve seed kaydedilir; farklı GPU/torch/CUDA sürümlerinde bit düzeyinde eşitlik garanti edilmez. Haricî deney takip entegrasyonları kapalıdır.

## Veri dönüşümü ve güvenli başlangıç politikası

`src/training/hit_uav_yolo.py`, mevcut güvenli `HitUAVArchive` ve doğrulanan normal_json adaptörünü kullanır. Format `images[].filename`, `annotation`, piksel `xmin,ymin,width,height`; sınıflar Person=0, Car=1, Bicycle=2, OtherVehicle=3, DontCare=4. Tek eğitim hedefi Person’dır. Her kutu sürekli 0 tabanlı piksel xyxy’den normalize merkez/boyuta çevrilir. Kaynak JSON, görüntüler, ZIP ve split üyeliği değiştirilmez. Yeniden boyutlandırma/augmentasyon yalnızca Ultralytics eğitim veri yükleyicisinde yapılır; hazırlanan görüntüler kaynakla byte-eşit kopyadır.

Bütün splitlerde aynı politika kullanılır:

- **Sıfır ham anotasyon:** görüntü dışlanır, inceleme bekliyor. Person sayısı sıfır olduğu için değil, bütün sınıflar dahil ham annotation sayısı sıfır olduğu için seçilir. Kullanıcının önceki 21/3/8 (toplam 32) sayısı referanstır; yeni çalıştırma bağımsız sayar. Negatif olduğu ilan edilmez.
- **DontCare içeren görüntü:** görüntünün tamamı dışlanır. Person kutuları varsa bunlar da bu deney kapsamına alınmaz, kayıp sayıları ayrıca raporlanır. Standart YOLO detect eğitim/değerlendirmesine desteklenmeyen ignore maskesi verilemez; DontCare’ı sıradan arka plan veya insan sınıfına çevirmek yerine bu başlangıç politikası kullanılır. Kırpma/maskeleme ile görüntü ve kutu semantiği değiştirilmez.
- **Diğer bilinen sınıflar:** Car/Bicycle/OtherVehicle kutuları YOLO hedeflerinden çıkarılır, görüntü korunur (DontCare/zero-raw dışlaması yoksa). Yalnızca bu sınıfları içeren görüntülerde boş YOLO etiketi vardır; bunlar Person açısından arka plan örneğidir. Bu karar **kalan görüntülerde Person anotasyonlarının tamlığı varsayımına** dayanır; anotasyonun kusursuzluğu iddia edilmez. Bu arka plan sayısı ayrı raporlanır.
- **Hatalı kaynak veya dönüşüm:** bilinmeyen sınıf, referans/ID/yol hatası, eksik/fazla görüntü, geçersiz/sınır dışı kutu, bozuk görüntü, 640×512 boyut uyuşmazlığı, desteklenmeyen mod/EXIF yönlendirmesi eğitim kapısını kapatır. Kutular kırpılmaz, hata sessizce filtrelenmez. Tekrarlanan Person satırları ve JPEG son işareti hataları, Ultralytics’in sessiz dedup/onarım işleminden önce reddedilir. Ultralytics’in bilinen üç labels/{split}.cache indeksi, eğitim sonrası hash/etiket denetiminde görüntü/etiket olarak sayılmaz; başka fazla dosyalar reddedilir. Hazırlanan her splitte en az bir görüntü ve Person kutusu olmalıdır.

Türetilmiş veri yerel `/content/therma-yolo-work/<run_id>/dataset/` altında `images/{train,val,test}` ve `labels/{train,val,test}` olarak oluşur; Colab kapanınca silinebilir ve kaynak ZIP’ten yeniden üretilebilir. Görüntü ID’siyle verilen çıktı adı ve özgün kaynak adı/üye yolu manifestte birlikte korunur. Her split için kaynak görüntü/sınıf sayıları, dışlanan görüntü ve Person kutuları, hazırlanmış görüntü/etiket/Person/arka plan sayısı yazılır. Notebook tüm kaynak görüntülerini gerçekten açar; sürüm ve önceki MD5 doğrulaması kullanıcı beyanıdır, yeni ZIP SHA256 ve JSON/görüntü/etiket hash’leri bu çalıştırmada hesaplanır.

YOLO çıktısı bağımsız tekrar okunur: sınıf 0, tam beş sütun, sonlu 0–1 normalize değerler, pozitif alan ve sınırlar kontrol edilir. Ters dönüşüm kaynak piksel kutusuyla 1e−5 piksel toleransında karşılaştırılır. Manifest, dosya seti, hash’ler ve split sayıları eğitim öncesi; görüntü/etiket kopyaları test öncesi yeniden denetlenir. `data.yaml` otomatik üretilir; train yalnızca train ve val yollarını kullanır, test sonradan ayrı çağrılır.

## Eğitim, seçim ve test protokolü

Kaynak sayım referansları: train 2029/8533, val 290/1168, test 579/2611 (görüntü/Person); toplam 2898/12312. Bu değerler kaynakta bağımsız yeniden sayılır. Filtrelenmiş deney sayıları daha düşük olabilir; özellikle DontCare dışlamasının etkisi veri okunmadan bilinemez. Test skoru **filtrelenmiş özgün test alt kümesine** aittir; tam HIT-UAV benchmark skoru olarak sunulamaz.

Validation her epoch çalışır. Ultralytics 8.3.228 best checkpoint fitness’i validation mAP@0.50:0.95’e dayanır; erken durdurma patience=10’dur. Efektif augmentasyon/optimizer/öğrenme oranları `args.yaml`, `effective_train_arguments.json`, `optimizer_effective.json` ve results.csv ile izlenir. `optimizer=auto` kütüphane varsayılanıdır; seçilen gerçek optimizer/grup başlangıç ayarları ayrıca kaydedilir. Train/validation loss ve metrikleri CSV, loss eğrileri PNG olarak saklanır. Best/last checkpoint’ler saklanır; bütün epoch’lara ait ayrı büyük model kopyaları üretilmez.

Eğitim tamamlandıktan sonra ayrı `YOLO(best.pt).val(split='test')` bir kez çağrılır. mAP@0.50 ve mAP@0.50:0.95, conf tabanı=.001, NMS IoU=.70 ve max_det=300 ile ölçülür; framework PR/diğer confidence eğrileri ve native confusion matrix kaydedilir.

Başlık **Precision/Recall** değerleri ayrı olarak önceden sabit confidence=.25, eşleme IoU=.50 ile bütün filtrelenmiş test görüntülerinde hesaplanır. Tahminler azalan confidence sırasında en yüksek IoU’lu eşleşmemiş GT’ye bire bir eşlenir; aynı GT’ye ikinci tahmin FP olur. Bu tanılama eşleyicisi Ultralytics/COCO mAP eşleyicisiyle aynı metrik iddiası taşımaz. Tahmin yoksa Precision tanımsız (`null`), GT varsa Recall=0’dır. Confusion matrix’te TN=N/A’dır. Native Ultralytics P/R test eğrisi optimumuna bağlı olabilir; operasyonel eşik seçimi veya başlık P/R metriği olarak kullanılmaz. Testten hiçbir hiperparametre/eşik seçilmez.

Tüm test tahminleri ve GT’leri JSONL, görüntü başına TP/FP/FN CSV; en fazla dört genel, dört FP ve dört FN karşılaştırması PNG olarak kaydedilir. GT kırmızı, tahminler mavi, FP mor ve kaçırılan GT turuncu kesiklidir. FP/FN örneği yoksa ilgili kategori boş kalır; örnek uydurulmaz. Örnekler alfabetik kaynak sırasından ilk uygun görüntülerdir ve hata dağılımının temsilî örneklemi değildir.

## Sızıntı ve sınırlılıklar

Önceki 1880 dHash adayı kullanıcı beyanıdır; bu eğitim hazırlığı dHash taramasını tekrar etmez ve aday sayısını kesin sızıntı sayısı olarak sunmaz. Kaynak dosya hash’leriyle kalan kopyalardaki split dışı tam byte-eşit gruplar ayrıca raporlanır; bunlar otomatik dışlanmaz ve split değiştirilmez. Yakın kareler, aynı uçuş/video/konum ve benzer sahneler nedeniyle test metrikleri iyimser olabilir. Bağımsız saha/uçuş genellemesi iddia edilmez. Bilimsel bir sonraki değerlendirme için güvenilir uçuş/sekans grupları ve kullanıcı tarafından onaylanmış protokol gerekir. WiSARD bu baseline’da eğitim veya test verisi değildir.

## Çıktılar ve API entegrasyonu

Drive run klasörü: `best.pt`, `dataset_manifest.json`, `image_dispositions.csv`, `data.yaml` (yerel kopyaya referans), `run_summary.json`, efektif parametreler, `ultralytics/train/` sonuçları/weights, `ultralytics/test/` sonuçları/eğriler, `test_diagnostics/` JSONL/CSV/PNG, `training_validation_losses.png`, `training_report.md` ve dosya SHA256 envanteri `artifacts.json`. Hazırlık/eğitim hatasında da mevcut tanılama ve kısmi dosyalar korunur; status başarılı olarak yazılmaz.

Model yükleme ve JSON inference örneği `src/evaluation/inference.py`, gelecekte FastAPI/Next.js entegrasyon gereksinimleri [ortak API sözleşmesi](inference_api_contract.md) içindedir. Frontend dosyalarına veya Claude’un branch’lerine müdahale edilmez. Checkpoint’ler ve gerçek görüntüler GitHub’a gönderilmez. AGENTS.md’deki eski Faz 1 kapsamını genişleten bu eğitim altyapısı kullanıcı tarafından bu görevde yetkilendirilmiştir; Codex ortamında gerçek eğitim başlatılması kapsam dışıdır.
