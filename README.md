# THERMA SEARCH AI

Termal İHA görüntülerinde derin öğrenmeyle insan tespiti için bilgisayar mühendisliği bitirme projesi. Uzun vadede afet sonrası bölgesel arama-kurtarma önceliklendirmesi, haritalama ve erişilebilir rota önerilerine temel oluşturacaktır.

**Faz 1:** Modüler Python altyapısı ve HIT-UAV keşif araçları. Henüz eğitim, model ağırlığı, model metriği veya gerçek veri seti ölçümü yoktur. YOLO11s ile başlanması, ardından RF-DETR Small karşılaştırılması planlanıyor.

## Başlangıç

Python **3.10+** ve CPU yeterlidir. Proje kökünde:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tests/validate_notebook.py
```

Windows etkinleştirme komutu: `.venv\Scripts\activate`. Notebook doğrulayıcı küçük sentetik veriler üretir; veri seti veya model indirmez. Çıktıları Git'e alınmayan `outputs/validation/` altına yazar.

## Web uygulaması (Faz 2, `web/`)

Therma Search AI operasyon arayüzü: Next.js (App Router) + React + TypeScript (strict) + Tailwind CSS v4. Python projesinden bağımsızdır; Node.js **20.9+** gerekir.

```bash
cd web
npm ci
npm run dev        # http://localhost:3000  (Detection Workspace'e yönlenir)
```

Üretim denemesi ve kontroller:

```bash
npm run build && npm run start   # üretim derlemesi
npm run lint
npm run typecheck
npm test                         # vitest birim testleri
```

**Önemli:** YOLO11s modeli ve FastAPI backend'i henüz bağlı değildir. Varsayılan `mock` modunda tarayıcı içi **DEMO / MOCK DATA** servisi çalışır: yüklediğiniz dosya gerçekten önizlenir/oynatılır, ancak kutular ve skorlar **yapay, tohumlu rastgele** değerlerdir ve görüntü içeriğiyle ilgisi yoktur; süreler simülasyondur. Dosyalar hiçbir yere gönderilmez. Gerçek istemci `NEXT_PUBLIC_THERMA_API_MODE=http` ile açılır (`web/.env.example`), ancak sözleşmeyi uygulayan bir backend olmadığı için gerçek sunucuya karşı denenmemiştir.

| Gerçek (çalışır) | Mock / henüz yok |
| --- | --- |
| Dosya seçme/sürükleme, tür-boyut doğrulaması, görüntü/video önizleme ve oynatma | Tespit kutuları ve skorlar (yapay) |
| Eşik filtresi, kutu/etiket/sınıf anahtarları, orijinal/işlenmiş/bölünmüş görünüm | Model çıkarımı, işlem süresi (simülasyon) |
| İş durumu akışı: hazır, işleniyor, başarılı, hata, iptal (hata mock'ta simüle edilir) | GPS, risk puanı, harita, rota, ekipler (yalnızca "Planlı" kartları) |
| İstatistik/histogram/zaman çizelgesi hesapları (verilen sonuç üzerinden) | Kalıcı analiz geçmişi, backend sağlık/yetenek bilgisi |

MP4 oynatma tarayıcının H.264 desteğine bağlıdır; çözülemeyen dosya açık hata mesajıyla reddedilir. API taslağı: [docs/api-contract.md](docs/api-contract.md). Tasarım sistemi: [docs/frontend-design-system.md](docs/frontend-design-system.md).

## Dosya ağacı

```text
therma-search-ai/
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
├── web/                     # Faz 2 web uygulaması (Next.js)
├── configs/
│   └── hit_uav.example.json
├── docs/
│   ├── api-contract.md
│   ├── frontend-design-system.md
│   ├── dataset_sources.md
│   ├── research_decisions.md
│   └── validation.md
├── notebooks/
│   └── 01_hit_uav_exploration.ipynb
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── inventory.py
│   │   ├── annotations.py
│   │   ├── audit.py
│   │   ├── download.py
│   │   └── exploration.py
│   ├── training/
│   │   └── __init__.py
│   └── evaluation/
│       └── __init__.py
└── tests/
    ├── test_data.py
    └── validate_notebook.py
```

`training/` ve `evaluation/` yalnızca yer tutucudur. `data/`, `outputs/`, `.venv/`, büyük görüntü/arşivler ve model ağırlıkları yok sayılır. Commit öncesi `git status --short` ile dosyaları ayrıca kontrol edin.

## Codex ve Claude Code

[AGENTS.md](AGENTS.md) ortak kuralların tek ana kaynağıdır. Codex bu dosyayı proje talimatı olarak kullanır. [CLAUDE.md](CLAUDE.md) ilk satırdaki `@AGENTS.md` ile aynı kuralları Claude Code'a aktarır; ardından yalnızca Claude Code'a özgü kısa kullanım notları bulunur. Ortak kuralları değiştirirken AGENTS.md güncellenir; iki dosyada kopya kurallar tutulmaz. Claude API, MCP, hook veya otomasyon kurulmadı.

## Colab'da notebook'u çalıştırma

1. `notebooks/01_hit_uav_exploration.ipynb` dosyasını Colab'a yükleyin veya kendi GitHub deponuzdan açın. CPU çalışma zamanı seçin.
2. **Proje kodunun tamamını** `/content/therma-search-ai` içine yükleyin veya kendi depo URL'nizle klonlayın. Notebook'u tek başına yüklemek `src/` modüllerini sağlamaz. Bu işlem veri setini sağlamaz.
3. Bir kurulum hücresinde `%pip install -r /content/therma-search-ai/requirements.txt` çalıştırın. Gerekirse notebook'taki `PROJECT_ROOT` yolunu ayarlayın.
4. Önce resmî Zenodo **v1.2.1** kaydının sabit ID'sini ve kullanım koşullarını doğrulayın. Metadata bölümünde `RECORD_ID` ve `CHECK_REMOTE_METADATA` ayarlayın. Bu bölüm yalnızca metadata alır.
5. Mevcut, bütünlüğü doğrulanmış veriyi Drive'dan bağlayıp `DATA_ROOT` seçin. Gelecekte indirmeye karar verirseniz notebook'taki **ayrı ve varsayılan kapalı** indirme/çıkarma bölümlerini kullanın; dosya adı ve boyut limitleri kullanıcı tarafından girilir.
6. Dosya ağacı ve ham etiketleri inceleyin. `configs/hit_uav.example.json` kopyasını gerçek şema, koordinat konvansiyonu ve mevcut split yollarıyla doldurun; `CONFIG_PATH` yolunu bu kopyaya yöneltin. `schema_confirmed` ancak bu incelemeden sonra `true` yapılmalıdır. Örnek config gerçek veri yolları içermez.
7. Sayım, kutu gösterimi ve kalite hücrelerini çalıştırın. `HASH_IMAGES=True` tam dosya kopyası kontrolünü açar. İsterseniz `SAVE_REPORT=True` ile raporu kaydedin. Boş veya hatalı veri ölçülmüş gibi sunulmaz.

Ayrıntılı kaynak/sürüm durumu ve WiSARD küçük örnek seçeneği: [docs/dataset_sources.md](docs/dataset_sources.md). Koordinat, sınıf sayımı ve metodoloji kararları: [docs/research_decisions.md](docs/research_decisions.md).

## Drive arşiviyle otomatik gerçek veri denetimi (Notebook 02)

[02_hit_uav_real_audit.ipynb](notebooks/02_hit_uav_real_audit.ipynb) mevcut ZIP'i **indirmeden ve tamamen çıkarmadan** okur. Kullanıcının Colab'da doğruladığı `annotation`, `filename`, piksel `xywh` ve 0–4 sınıf eşlemesi için ayrı HIT-UAV adaptörü kullanır. Notebook 01 ve genel COCO/VOC okuyucuları korunmuştur.

1. [Notebook 02'yi Colab'da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/feature/hit-uav-leakage-review/notebooks/02_hit_uav_real_audit.ipynb) ve CPU çalışma zamanında hücreleri sırayla çalıştırın. Kod revizyonu notebook içinde sabitlenir; rapora gerçek commit yazılır.
2. İlk hücre public kod deposunu hazırlar ve yalnızca `requirements-colab.txt` paketlerini `--no-deps` ile kontrol eder. **Ana requirements.txt'yi Colab'da kurmayın:** bu hafif yol ipykernel/jupyter-client paketlerini değiştirmez; mevcut Pillow 11.3.0 ve Matplotlib 3.10.0 aralıklarla uyumludur.
3. Drive bağlantısına izin verin. Varsayılan arşiv: `/content/drive/MyDrive/ThermaSearchAI/datasets/hit_uav_v1.2.1.zip`. Yolunuz aynıysa ek ayar gerekmez. Mevcut ZIP bulunamazsa indirme yerine açık hata verilir.
4. Kalıcı çıktılar `/content/drive/MyDrive/ThermaSearchAI/reports/hit_uav/run_.../` içine otomatik kaydedilir: sınıf ve Person boyut grafikleri, varsayılan üç kutulu örnek PNG, split CSV'si, kalite JSON'u ve sürüm/tarih/commit/yapılandırma metadata'sı. Önceki raporlar korunur; tüm görüntüler yeniden kaydedilmez.

Önceki kullanıcı sayımları train **2029/8533/17628**, val **290/1168/2460**, test **579/2611/4811** (görüntü/Person/nesne) yalnızca karşılaştırma referansıdır. Notebook bunları yeniden hesaplar, uyuşmazlığı gösterir. Yaklaşık 12×19 medyanı sonuca kopyalanmaz. DontCare korunur. Ortak dosya adı kontrolü yakın kare/aynı uçuş sızıntısını kanıtlamaz veya dışlamaz; splitler değişmez.

Bu geliştirme ortamında gerçek Drive arşivi erişilebilir değildir; yeni akış sentetik ZIP ile sınanmıştır. Kullanıcının önceki MD5 doğrulaması metadata'da **kullanıcı beyanı** olarak saklanır; bu çalıştırmada yeniden MD5 hesaplandığı iddia edilmez. Okunan üyelerde ZIP CRC denetlenir. Raporlama ve kapsam ayrıntıları notebook'tadır.

## Notebook 02: etiketsiz görüntüler ve sızıntı denetimi

Notebook 02'nin sonuna **9–11. bölümler** eklendi; Notebook 01 değişmedi. Güncel notebook'u açıp ilk kurulum/Drive/ZIP hücreleriyle mevcut analizi çalıştırın; ardından **9 · yapılandırma**, **10 · tarama/kayıt**, **11 · görsel inceleme** hücrelerini sırayla çalıştırın. Yeni bölümler `src/data/leakage.py` ve `leakage_reports.py` modüllerini kullanır; bootstrap kod referansı bu modülleri içeren sürüme sabitlenir. Yeni notebook'u temiz Colab CPU çalışma zamanında açın.

Sıfır **ham** anotasyonlu görüntüler seçilir; kullanıcının bildirdiği 21/3/8 sayıları yeniden hesaplanıp karşılaştırılır. Her splitin tüm contact sheet sayfaları gösterilir; dosya adları ve `review_id` ile eşleşen `manual_review.csv` dosyasında insan varlığını elle değerlendirin. İnsan kararı alanları boş bırakılır; otomatik negatif kabulü veya etiket değişikliği yapılmaz. DontCare anotasyon sayılır. Hatalı kutudan dolayı boş kalan veya görüntü kaydı eksik olan örnekler ayrı gerekçeyle işaretlenir.

Kaynak ZIP'teki görüntü dosya baytları ve ayrıca doğal mod/boyut/pikseller için SHA256 hesaplanır. **Tam kopya örtüşmeleri**, 64 bit dHash **Hamming ≤4** yakınlık adaylarından ayrı raporlanır. Eşik ve çıktı limitleri 9. bölümde ayarlanır. Tekdüze termal sahneler yanlış benzerlik üretebilir; görsel benzerlik kesin sızıntı değildir. Dosya adı grupları doğrulanmamış hipotezdir; uçuş kimliği değildir. Yakın uçuş karelerini kaçırma olasılığı devam eder.

Yeni paket aynı Drive kökünde `run_leakage_.../` dizinine kaydedilir: contact sheet PNG'leri, manuel CSV, hash envanteri, exact çift CSV/tüm grup JSON'u, near aday CSV'si, en fazla 12 çift görseli, dosya adı hipotezleri ve kapsam/hata/limit/kaynak bilgili özet JSON. Eski raporlar ve kullanıcı kararları korunur. Tüm split-dışı okunabilir çiftler taranır; CSV sınırına ulaşılırsa toplam ve kesilme durumu açıkça kaydedilir. Ayrıntılar: [docs/leakage_review.md](docs/leakage_review.md).

## WiSARD: Tümünü çalıştır (Notebook 03)

[Notebook 03’ü Colab’da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/03_wisard_exploration.ipynb), CPU çalışma zamanında **Çalışma zamanı → Tümünü çalıştır** seçin. İlk Drive bağlantısında Google erişim izni gerekebilir. Hücre, regex, PairingSpec/LabelSpec veya kare numarası girmeniz gerekmez.

Varsayılan mevcut ZIP: `/content/drive/MyDrive/ThermaSearchAI/datasets/WiSARD_Multi_Modal_Sample.zip`. Notebook bilinen MtErie IR/VIS örneğinde bütün görüntü/etiketleri yeniden sayar; bütünlük, sınıflar, boş/eksik etiketler, kutu boyutları, count.txt, iki eşleştirme hipotezi ve modalite içi dHash/SHA benzerliği denetimini çalıştırır. Her hipotezden yeterli aday varsa 10 farklı kare ground-truth kutularıyla kaydedilir. Yeni run klasöründeki CSV/JSON, 200 DPI PNG ve akademik Markdown raporu otomatik olarak `/content/drive/MyDrive/ThermaSearchAI/reports/wisard/run_wisard_.../` altına yazılır. Önceki raporlar korunur.

IR n ↔ VIS n ve IR n ↔ VIS n−1 ayrı raporlanır. Tercih **geçici hipotezdir**; sayı uyumu/EXIF saat adayı fiziksel senkronizasyonu kesinleştirmez. İnsan anotasyonu benzersiz kişi sayısı değildir; IR/VIS sayımları ayrı tutulur. Boş TXT otomatik negatif kabul edilmez. Bilinmeyen ZIP’te etiket/eşleştirme tahmini yapılmadan açık tanılama raporu üretilir. ZIP yoksa indirilmez; hata kaydı yazılır. Eğitim ve rastgele split oluşturulmaz.

Notebook 01/02, HIT-UAV analizleri, veri dosyaları ve eski raporlar korunur. Gerçek WiSARD ZIP’i geliştirme ortamında erişilebilir değildir; doğrulama sentetik fixture ve notebook yürütmesiyle yapılır. [Yöntem ve çıktıların ayrıntıları](docs/wisard_exploration.md) · [Yeni doğrulama kaydı](docs/validation_wisard_one_pass.md).

## Bağımlılıklar

| Doğrudan bağımlılık | Kullanım |
| --- | --- |
| Pillow | Görüntü çözünürlüğü, piksel yükleme ve bütünlük kontrolü |
| Matplotlib | Sınıf/çözünürlük dağılımı ve kutulu örnekler |
| nbformat | Notebook üretimi ve şema doğrulama |
| nbclient | Hücreleri baştan sona çalıştırma |
| ipykernel | Python notebook çekirdeği |

Testler standart `unittest` kullanır; pytest gerekmez. Aralıklar requirements.txt içindedir; tam ortam kilidi değildir. Her keşif raporu kullanılan sürümleri kaydeder. Eğitim bağımlılıkları sonraki aşamada, kullanıcı onaylı plana göre eklenecektir.

## Doğrulama ve sınırlar

Gerçekten çalıştırılan kontroller ve sonuçları [docs/validation.md](docs/validation.md) içinde kayıtlıdır. Sentetik testler gerçek HIT-UAV doğrulaması değildir.

İlk Faz 1 tesliminde Zenodo ve WiSARD proje sitesine bu Cloud ortamından erişim politikayla engellendi. Bu nedenle Zenodo v1.2.1 kayıt ID'si/lisansı/checksum'ları ve WiSARD dağıtım sürümü/örnek bağlantısı henüz doğrulanamadı. Görüntü sayıları, çözünürlükler, DontCare ayrıntıları, gerçek etiket şeması ve split üyelikleri yerel veri üzerinde henüz ölçülmedi. Genel COCO/VOC adaptörlerinin gerçek dağıtımla uyumu da doğrulanmayı bekliyor.

**Bir sonraki adım:** Notebook 02 ile mevcut Drive arşivindeki sayımları yeniden üretmek ve kalıcı kalite raporlarını incelemek; lisans/sızıntı incelemesini ayrıca tamamlamak. Eğitimden önce DontCare ve sızıntı/değerlendirme protokolü için kullanıcı onayı alınacaktır.

## İlk YOLO11s eğitimi (Notebook 04)

[Notebook 04’ü Colab’da açın](https://colab.research.google.com/github/hilalaltunayy/therma-search-ai/blob/main/notebooks/04_hit_uav_yolo_training.ipynb), **GPU** çalışma zamanı seçip **Tümünü çalıştır** deyin. İlk Drive bağlantı izni gerekebilir. Mevcut `ThermaSearchAI/datasets/hit_uav_v1.2.1.zip` otomatik okunur; veri doğrulanır, Person-only YOLO kopyası hazırlanır, 40 epoch/patience 10 ile YOLO11s eğitilir ve validation ile seçilen `best.pt` ayrı test edilir. GPU yoksa CPU eğitimi başlamaz. Gereken pretrained ağırlık Colab’da indirilir; model/veri sonuçları bu geliştirme tesliminde üretilmiş değildir.

Güvenli başlangıç politikası: sıfır **ham** anotasyonlu ve DontCare içeren görüntüler bütün splitlerden türetilmiş kopyada dışlanır; diğer sınıf kutuları hedef dışı arka plandır. Dışlanan görüntü/Person sayıları ve kalan Person-arka plan örnekleri ayrı raporlanır. Kaynak veriler ve özgün split üyelikleri korunur. Veri/dönüşüm hatası varsa eğitim başlamaz. Sonuçlar filtrelenmiş test alt kümesindeki **exploratory baseline**’dır; bildirilen 1880 dHash adayı nedeniyle bağımsız saha genellemesi iddia edilmez.

Çıktılar `ThermaSearchAI/runs/hit_uav_yolo11s/run_yolo11s_.../` altında Drive’a kaydedilir: best.pt, manifest, train/validation loss/metrikleri, ayrı test mAP ve sabit eşikte Precision/Recall, PR eğrileri, confusion matrix, GT/prediction ve FP/FN örnekleri, süre/GPU/sürüm/parametreler. Ağırlıklar GitHub’a gönderilmez. Notebook 01–03 ve frontend dosyaları değiştirilmez.

[Çalıştırma, veri politikası ve bilimsel kapsam](docs/yolo11s_baseline.md) · [FastAPI/Next.js ortak inference sözleşmesi](docs/inference_api_contract.md) · [Doğrulama kaydı](docs/validation_yolo11s_baseline.md). Eğitim bağımlılığı ayrı `requirements-training-colab.txt` içindedir.
