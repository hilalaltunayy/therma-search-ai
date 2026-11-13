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

## Dosya ağacı

```text
therma-search-ai/
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
├── configs/
│   └── hit_uav.example.json
├── docs/
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

Zenodo ve WiSARD proje sitesine bu Cloud ortamından erişim politikayla engellendi. Bu nedenle Zenodo v1.2.1 kayıt ID'si/lisansı/checksum'ları ve WiSARD dağıtım sürümü/örnek bağlantısı henüz doğrulanamadı. Görüntü sayıları, çözünürlükler, DontCare ayrıntıları, gerçek etiket şeması ve split üyelikleri yerel veri üzerinde henüz ölçülmedi. Genel COCO/VOC adaptörlerinin gerçek dağıtımla uyumu da doğrulanmayı bekliyor.

**Bir sonraki adım:** Colab'da resmî v1.2.1 metadata ve lisansını doğrulamak; ardından kullanıcı tarafından sağlanacak veride ham şema, mevcut splitler ve kutu örneklerini incelemek. Eğitimden önce DontCare ve sızıntı/değerlendirme protokolü için kullanıcı onayı alınacaktır.
