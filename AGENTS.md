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

## Faz 2 — Web uygulaması (`web/`)
Faz 1 kuralları ve bilimsel güvenlik kuralları aynen geçerlidir. Next.js (App Router) + React + TypeScript (strict) + Tailwind uygulaması `web/` altındadır; Python kodu, notebook'lar, veri/model dosyaları ve Faz 1 testleri bu kapsamda **değiştirilmez**.
- Frontend/uygulama işi Claude Code tarafında, model eğitimi/veri hazırlığı Codex tarafında yürür; ayrı feature branch'lerde çalışılır, main'e doğrudan push yapılmaz, PR otomatik merge edilmez.
- Frontend ↔ backend sözleşmesi [docs/api-contract.md](docs/api-contract.md) dosyasındadır; koordinat konvansiyonu ve sınıf eşlemesi değişikliği kullanıcı onayı ister. Tasarım sistemi: [docs/frontend-design-system.md](docs/frontend-design-system.md).
- Mock/demo veri **her zaman** "DEMO / MOCK DATA" olarak etiketlenir; gerçek model çıktısı, gerçek GPS/risk/operasyon verisi gibi sunulmaz. Backend'de olmayan uç noktalar çalışıyormuş gibi gösterilmez.
- Web komutları (`web/` içinde): `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run dev`.

## Çalışma komutları
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q src tests
```
Notebook doğrulama yönergesi: `docs/validation.md`. Ortak kuralları CLAUDE.md içine kopyalama; değişiklikleri burada tut.
