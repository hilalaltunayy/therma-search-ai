# THERMA SEARCH AI — Ortak mühendislik talimatları

Bu dosya Codex ve Claude Code için ortak talimatların ana kaynağıdır.

- Modüler, okunabilir, test edilebilir Python kodu yaz. Önemli fonksiyonları, kütüphane seçimlerini ve dönüşümlerin girdi/çıktı biçimlerini açıkla.
- Önemli teknik değişikliklerin gerekçesini açıkla; araştırma kararlarını ve belirsizlikleri belgele.
- Veri sızıntısı, hatalı etiketler ve değerlendirme metodolojisini denetle. Aynı uçuş, video, konum ve yakın karelerin bölümler arasında bulunmasını araştır.
- Train/validation/test sınırlarını kullanıcı onayı olmadan değiştirme. Keşif araçları kaynak veriyi değiştirmesin.
- Model eğitimi, büyük indirmeler ve maliyetli işlemler için önceden kullanıcı onayı iste. İndirme hücreleri varsayılan olarak kapalı olsun.
- Gerçekleştirilmemiş deneyleri yapılmış gibi gösterme. Metrikleri, model sonuçlarını veya veri seti özelliklerini uydurma. Kaynak beyanı ile yerel ölçümü ayır.
- HIT-UAV için resmî Zenodo v1.2.1 kaydını esas al; sürümü, lisansı ve checksum değerlerini doğrula. GitHub klonunun gerçek veriyi içerdiğini varsayma.
- WiSARD tam arşivini otomatik indirme. Önce resmî kaynak/sürüm ve küçük örnek arşiv seçeneğini doğrula.
- Gizli anahtarları, kişisel bilgileri, büyük veri dosyalarını, model ağırlıklarını ve geçici çıktıları GitHub'a gönderme. `.gitignore` tek başına güvence değildir; commit öncesi dosya listesini incele.
- Kod değişikliklerinden sonra uygun testleri çalıştır. Veri yoksa sentetik testleri gerçek veri doğrulaması olarak sunma.
- İşin sonunda değiştirilen dosyaları, gerçekten çalıştırılan testleri ve açık kalan sorunları raporla.
- Eğitim ve bilimsel değerlendirme kararlarında son onayı kullanıcıya bırak. DontCare, sınıf eşleme, koordinat konvansiyonu ve değerlendirme protokolünü sessizce değiştirme.

## Faz 1 kapsamı
Python 3.10+; CPU ile keşif ve birim testleri. Eğitim, model ağırlığı, bulut otomasyonu, Claude API, MCP ve hook kurulumu bu aşamanın dışında.

## Çalışma komutları
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q src tests
```
Notebook doğrulama yönergesi: `docs/validation.md`. Ortak kuralları CLAUDE.md içine kopyalama; değişiklikleri burada tut.
