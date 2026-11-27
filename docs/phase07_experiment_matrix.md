# Faz 07 — Kontrollü ikinci eğitim matrisi (öneri, çalıştırılmadı)

Bu plan hiçbir eğitim başlatmaz. Kaynak **HIT-UAV train + özgün filtered validation** dışında confidence, hiperparametre veya checkpoint seçimi yapılmaz. WiSARD artık incelenmiş tanılama verisidir; pristine final holdout değildir. HIT-UAV test de geliştirme/arm seçimi için kullanılmaz.

## Önkoşullar ve kontrol bloğu

Gerçek baseline `args.yaml`, `effective_train_arguments.json`, `optimizer_effective.json`, başlangıç pretrained SHA256 ve veri üyeliği manifesti doğrulanmadan deney başlatılmaz. Eksik etkin ayarlar uydurulmaz. Özellikle `optimizer=auto`, batch/iterasyon sayısı değişince optimizer seçimini değiştirebilir; aynı gerçek optimizer, öğrenme oranı, scheduler ve ağırlık decay ayarları açıkça sabitlenmelidir.

Önerilen yeni ortak blok batch=4, FP32, seed=42, epochs=40, patience=10, aynı pretrained başlangıç, aynı Person/DontCare/sıfır-ham-anotasyon politikasıdır. Batch=4 **henüz ölçülmüş uygunluk sonucu değildir**; kaynak train verisi üzerinde bellek ön kontrolü ve kullanıcı onayı gerekir. 960 sığmazsa bütün yeni blok için batch düşürülüp kontrol yeniden çalıştırılır. Yalnız yüksek çözünürlük kolunda batch değiştirmek çözünürlük etkisini karıştırır.

Eski batch=8 baseline ile yeni batch=4 kontrol doğrudan tek-faktör nedensel karşılaştırma sayılmaz: bu bir köprü/yeniden üretilebilirlik kontrolüdür. Kaydedilen eski etkin optimizer/schedule ile eşdeğerlik kontrol edilmelidir. Aşağıdaki ana karşılaştırmalar **yeni ortak kontrol P07-C0** üzerinden yapılır.

| Kol | Karşılaştırma | Tek ana faktör | Önerilen değişiklik | Kaynak-veri gerekçesi ve olası bedel |
|---|---|---|---|---|
| P07-C0 | Yeni ortak kontrol | Yok | imgsz=640, diğer etkin baseline ayarları | Yeni blok için tekrarlanabilir referans; eski run’a atıfla kazanım iddiası değil |
| P07-R1 | C0 | Çözünürlük politikası | imgsz=960 | Kaynak küçük GT’lere daha fazla ağ pikseli; sensör ayrıntısı eklenmez. Eğitim/validation/inference çözünürlüğü birlikte değişir: izole eğitim kazanımı değil sistem çözünürlüğü etkisidir. Yaklaşık 2.25 kat piksel maliyeti; bellek ve gecikme ölçülür |
| P07-A1 | C0 | Rastgele scale augmentasyon aralığı | scale=0.25 | Gerçek baseline scale=0.5 ise daha az agresif küçültme küçük kaynak hedefleri koruyabilir. Ölçek çeşitliliği azalabilir; kazanç varsayılmaz |
| P07-A2 | C0 | Mosaic olasılığı | mosaic=0.0 | Kontrol mosaic etkinse, küçük insanları küçülten kompozisyonları kaldırma adayı. Arka plan çeşitliliği/regularization azalabilir |

Kontroldeki gerçek değer adayla aynıysa o kol atlanır; yapılmış değişiklik gibi raporlanmaz. Scale ve mosaic aynı kolda değiştirilmez. Mosaic kapatma kolunda close_mosaic gibi diğer ayarlar sabit kalır; mosaic zaten kapalı olduğunda son-epoch kapatma ayarı etkisizdir. Henüz nedensel kanıt veya üstün kol yoktur.

## Önceden sabit seçim ve raporlama

Birincil seçim metriği kaynak filtered validation native mAP50:95’tir. Aynı GT’ler üzerinde küçük nesne recall’u (açık width<16/height<16/both<16 paydaları), sabit conf=.25 / IoU=.50 FP-görüntü, kaynak hataları, bellek ve gecikme yardımcı ölçümlerdir. Kaynak train/val boyut/kontrast tanılaması adayın uygunluğunu değerlendirmek içindir; WiSARD skorları aday/threshold/seed seçmez. P07-R1 için değerlendirme çözünürlüğü değişimi raporda açıkça tutulur; sırf daha fazla hesapla kazanım, öğrenilmiş temsilin tek başına iyileşmesi sayılmaz.

İlk seed=42 keşif bloğundan sonra kaynak-val ile kısa listeye alınan kollar ve eşlenmiş kontrol 42/43/44 seed’leriyle tekrarlanır. En iyi seed seçilip diğerleri gizlenmez; tüm sonuçlar, ortalama/std, erken durdurma epoch’u, OOM/başarısız run’lar ve etkin ayarlar kaydedilir. Seed std bağımsız uçuş belirsizliği değildir. Gürültü düzeyindeki farklarda daha basit/ucuz kol tercih etme kuralı önceden kararlaştırılmalıdır. Kombinasyon/etkileşim kolları için ayrı ön kayıt gerekir.

Checkpoint seçimi yalnız ilgili run’ın kaynak validation fitness’iyle yapılır. Bu validation eski baseline seçiminde zaten kullanılmıştır ve bilinen yakın-kare/split-sızıntısı riski taşır; nihai genelleme kanıtı olarak kullanılamaz. Özgün splitler bu planla sessizce değiştirilmez. Yeni flight-group protokolü gerekirse ayrı kullanıcı onayı ve sürümlü veri planı gerekir.

## Yeni bağımsız dış değerlendirme

Son model/protokol dondurulduktan sonra açılacak, farklı uçuş/görev/saha ve çekim koşullarından oluşan yeni bir dış küme gerekir. Yakın kareler/aynı olay tek grup tutulmalı; sahne/etiket kapsamı, doğrulanmış negatifler ve insan anotasyonu kalitesi bağımsız incelenmelidir. Bu küme model hatalarına bakılarak örnek seçme veya threshold ayarlama amacıyla kullanılmaz. Operasyonel yanlış alarm için belirsiz boş TXT yerine doğrulanmış negatif sahneler gerekir. Tekrar bakılmış WiSARD sonuçları ancak ikincil tanılama bağlamı olarak raporlanır.

Makine tarafından okunabilir öneri: `configs/phase07_experiment_matrix.json`. Dosya yürütülebilir eğitim komutu değildir; gerçek etkin parametreler ve onay çözülmeden eğitim başlatılmaz.
