# Faz 1 doğrulama kaydı

Tarih: **2026-11-13**. Çalışma dizini: proje kökü. Bu kayıt model deneyi veya gerçek veri doğrulaması değildir.

## Ortam

Python 3.12.14; proje yerel `.venv` ortamı. Çalışma ortamının mevcut paketleri kullanılmış, eksik notebook bağımlılıkları ve requirements aralığına uygun Pillow bu sanal ortama kurulmuştur. requirements.txt tam sürüm kilidi değildir.

| Doğrudan paket | Kontrollerde kullanılan sürüm |
| --- | --- |
| Pillow | 12.3.0 |
| Matplotlib | 3.10.8 |
| nbformat | 5.11.1 |
| nbclient | 0.11.0 |
| ipykernel | 7.4.0 |

## Gerçekten çalıştırılan kontroller

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/validate_notebook.py
.venv/bin/python -m compileall -q src tests
git diff --check
```

- **17 birim testi geçti.** Koordinat dönüşümleri; negatif/NaN/açılı kutu reddi; COCO ID ilişkileri ve tekrarları; DontCare/negatif örnek koruması; VOC konvansiyonları; gerçek piksel boyutu ve bozuk görüntü; eksik görüntü ve eşleşmeyen etiket; sınır dışı kutu; bölüm içi/dışı aynı dosya hash'i; eksik config; kısmi ayrıştırma hatası; çizilen kutu konumu; yol traversal; ZIP limitleri ve çıkarma; indirme onayı; checksum/manifest; hatalı indirme temizliği; sürüm uyuşmazlığı sınandı.
- **Notebook nbformat şema doğrulaması geçti.** Kaynak notebook 24 hücrelidir; çalışma çıktıları kaynak dosyaya yazılmadı.
- **Verisiz varsayılan akış baştan sona geçti.** Metadata/indirme kapalı, sayımlar yapılmadı mesajları doğrulandı. Sahte sıfır veri bulgusu üretilmedi.
- **Sentetik veri akışı baştan sona geçti.** Test için geçici olarak üç split oluşturuldu; her birinde iki yapay 20×10 görüntü, bir Person ve bir DontCare kutusu, bir boş anotasyon kaydı vardı. Bu sayılar yalnızca test girdisidir. Tüm notebook hücreleri yürütüldü; **12 grafik/görsel çıktısı** oluştu. Seçili sınıf sayıları ve sıfır ayrıştırma hatası çıktıdan kontrol edildi.
- **Görsel inceleme:** Sentetik sınıf dağılımı, çözünürlük dağılımı ve Person/DontCare kutulu örneği PNG olarak açılıp incelendi. Başlık/eksenler okunuyor; kutular sentetik koordinatlarla uyumlu; DontCare kesik turuncu çizgiyle ayrılıyor. Notebook'un Colab arayüzündeki görünümü ayrıca denenmedi.
- `compileall` ve `git diff --check` başarılı tamamlandı.
- `git check-ignore` ile veri arşivi, model ağırlığı, `.env`, `.venv` ve üretilen çıktıların yok sayıldığı kontrol edildi. Kaynak notebook küçük ve çıktı hücreleri boş. Commit/push veya GitHub değişikliği yapılmadı.

Notebook doğrulama betiği bağımsız kernel kullanır. Son çalıştırmadan üretilen inceleme dosyaları `outputs/validation/default_no_data.executed.ipynb`, `outputs/validation/synthetic_only.executed.ipynb` ve örnek PNG'lerdir. Bunlar Git tarafından yok sayılır; sentetik notebook açıkça etiketlidir ve geçici veri yolları yeniden çalıştırılabilir gerçek veri referansı değildir. Yeniden üretmek için betiği çalıştırın.

## Sınanmayanlar / açık kalanlar

- Gerçek HIT-UAV arşivi indirilmedi/açılmadı. Gerçek şema, koordinat kökeni, çözünürlükler, sınıf sayıları, split üyelikleri ve DontCare semantiği ölçülmedi.
- Zenodo API ve WiSARD proje sitesine ortam politikası erişimi engelledi. Canlı metadata/indirme uçtan uca sınanmadı. İndirme testleri `unittest.mock` ile küçük bellek akışlarını kullanır; gerçek ağ isteği yapmaz.
- WiSARD küçük örneğinin indirme bağlantısı, sürümü, lisansı, boyutu ve checksum'ı birincil dağıtımdan doğrulanmadı.
- COCO/VOC adaptörlerinin v1.2.1 gerçek dağıtımına uygunluğu doğrulanmadı. Desteklenmeyen şema gelirse ham örneğe göre adaptör eklenecek.
- Dosya SHA256 kontrolü yalnızca tam bayt kopyalarını yakalar. Görsel yakınlık, çekim grupları, coğrafi sızıntı ve insan tarafından eksik etiket incelemesi yapılmadı.
- Python 3.10/3.11 ve gerçek Google Colab çalışma zamanı ayrıca sınanmadı. Gerekli kullanıcı adımları README ve notebook'ta bulunur.
- Eğitim, YOLO11s/RF-DETR çıkarımı, ağırlık indirmesi veya model değerlendirmesi yapılmadı.
