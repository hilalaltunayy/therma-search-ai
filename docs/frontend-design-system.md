# Therma Search AI — web tasarım sistemi (v0.2)

Hedef: arama-kurtarma İHA görüntü analizinde kullanılabilecek, ciddi ve okunaklı bir **Mission Control** arayüzü. Token'ların tek kaynağı [`web/src/app/globals.css`](../web/src/app/globals.css) (`@theme` ve `@layer components`).

> Uygulama henüz gerçek backend'e bağlı değildir. Mock sonuçlar her ekranda amber **DEMO / MOCK** etiketi taşır.

## Renk rolleri

| Rol | Token | Değer | Nerede |
| --- | --- | --- | --- |
| Zemin | `base` / `deep` | `#080D17` / `#04070D` | sayfa zemini / görüntüleme sahnesi |
| Yüzey | `surface` / `surface-2` / `raised` | `#182535` / `#111B2A` / `#1E2D41` | opak paneller, kontroller, hover |
| Çizgi | `line` / `line-strong` | %12 / %24 slate | 1 px çerçeveler |
| Metin | `ink` / `muted` / `subtle` / `disabled` | `#E8EEF7` / `#A3B1C6` / `#8A9AB2` / `#5D6B80` | `subtle` raised üzerinde 4.87:1 |
| **Cyan** | `cyan` | `#22C9D9` | aktif teknik kontroller, birincil eylem, **tüm tespit kutuları** |
| **Mor** | `purple` / `violet` | `#7556B8` / `#A38BE0` | yalnız **seçim ve odak**: seçili tespit (kart + kutu), eşik çizgisi, cam üst kenar ışığı. `purple` metinde kullanılmaz (yüzeyde 2.79:1) |
| **Koyu turuncu** | `orange` / `orange-text` | `#BD6542` / `#DE8A66` | **zaman** (oynatma imleci, HUD zaman değeri) ve marka işareti. Küçük metinde yalnız `orange-text` (5.86:1) |
| **Amber** | `amber` | `#F0A345` | yalnız **DEMO / MOCK** ve uyarı; tespit kutularında hiç kullanılmaz |
| Hata | `danger` | `#F47078` | hata metni ve durumları (yüzeyde ≥4.5:1) |

Kutular neden cyan: termal paletler sıcak tonludur (mor-turuncu-sarı); sıcak renkli kutular termal imzada kaybolur. Skor bandı renkle değil **çizgi stiliyle** ayrılır (skor < 0.50 kesikli). Bu yalnızca görsel ayrımdır, güvenilirlik sınıflandırması değildir.

## Cam (glassmorphism) katmanları

| Sınıf | Kullanım | Yapı |
| --- | --- | --- |
| `.glass` (+ `.glass-edge`) | Inspector, analitik panelleri, açılır bilgi paneli, genişletilmiş menü | yarı saydam koyu gradyan, `blur(16px) saturate(150%)`, ince açık kenar, iç üst yansıma; `.glass-edge` üst kenara cyan→violet ışık çizgisi ekler |
| `.glass-card` | tespit kartları, metrik kartları, S&R / Lab kartları | daha hafif cam; hover/seçim/odak durumları (aşağıda) |
| `.hud-chip` | görüntü çevresindeki HUD etiketleri | küçük yoğun cam, monospace |

Camın görünmesi için zeminde kontrollü ton farkı vardır: sağ üstte mor, sağ altta ve sol altta cyan ışık alanları ve çok düşük opaklıkta topoğrafik eş yükselti halkaları (`body` arka planı). Görüntüleme sahnesi opaktır (`deep`); termal görüntünün üzerine cam panel yerleşmez. HUD çipleri karenin **dışındaki** satırlardadır, tespitleri örtmez.

## Etkileşim durumları

| Durum | Görsel karşılık (150–250 ms, ease-out, transform/opacity/renk) |
| --- | --- |
| Hover (`.glass-card`) | kenar cyan'a yaklaşır, iç ışık ve imleci izleyen cyan/mor yansıma belirir, 1 px yükselir. Yalnız `@media (hover: hover)` |
| Seçim (`data-selected`) | violet kenar + mor dolgu + ince halka; hover'dan bağımsız ve kalıcı. Görüntüdeki kutu aynı anda violet ve 2 px |
| Kart/kutu hover eşleşmesi | listedeki karta gelince görüntüdeki kutu açık cyan ve kalınlaşır (ve tersi); yalnız ilgili kutu vurgulanır |
| Focus | 2 px cyan dış halka (`:focus-visible`) |
| Active | `scale(0.98–0.995)` basma geri bildirimi |
| Disabled | `disabled` metin rengi, kesikli kenar, imleç `not-allowed` |

`prefers-reduced-motion` tüm geçiş ve animasyonları kapatır. Dokunmatikte hover'a bağlı bilgi yoktur: tooltip içerikleri ayrıca erişilebilir ad olarak verilir, "Bu nedir?" açıklaması tıklamayla açılır.

## Tipografi

Sistem yazı tipi yığını (ağ bağımlılığı yok). Gövde 14–15 px, teknik etiketler en az 12 px, sayılar ve koordinatlar monospace `tabular-nums`. Skor değerleri kartta 16 px kalın, eşik değeri 28 px.

## Yerleşim

```text
AppShell: 72 px ikon rayı (tooltip + genişletilebilir cam menü) · 56 px üst çubuk (DEMO, API, model çipleri)
Detection Workspace (lg+, yükseklik = görünüm alanı):
  ┌ görüntü sütunu ───────────────────────────────┐ ┌ Inspector 372 px (veya 72 px şerit) ┐
  │ araç çubuğu: dosya · Tespitli/Orijinal/Karşılaştır · Kutular/Skorlar │ Analiz görevi (her zaman)          │
  │ sahne: HUD satırı · kare (cetvel, köşe işaretleri) · DEMO satırı     │ Güven eşiği + mini histogram        │
  │ sabit oynatıcı: geri/oynat/ileri · zaman · zaman çizelgesi · hız     │ sekmeler: Tespitler · Görev · Görünüm │
  └──────────────────────────────────────────────┘ └────────────────────────────────────┘
```

- Sahne kapsayıcı boyutundan (container query) hesaplanır; 1366×768'de oynatıcı ve zaman çizelgesi sayfa kaydırması olmadan görünür.
- Inspector daraltıldığında 72 px şerit durum, karedeki tespit sayısı, eşik ve birincil eylemi korur. Tercih tarayıcıda hatırlanır.
- `<lg`: tek sütun; sahne, oynatıcı, inspector alt alta. Daraltma yalnız masaüstünde geçerlidir.
- Etiket yerleşimi `lib/detections/labels.ts`: yakın tespitlerde etiketler çakışmaz ve başka bir kişinin kutusunu örtmekten kaçınır. Kutu geometrisi değişmez.

## Sayılar ve dürüstlük kuralları

- "Bu karede n / m": geçerli karede eşik üstü / toplam. "Tüm kareler (kare toplamı)": video boyunca toplam; **benzersiz kişi sayısı değildir** (izleme yok).
- `#n` kare içi sıradır (en yüksek skor #1), izleme kimliği değildir.
- HUD yalnız gerçek değer gösterir: medya boyutu, oynatma zamanı, sayılar, eşik. FPS, GPS, sıcaklık, telemetri veya model metriği gösterilmez.
- Planlı alanlar (operatör doğrulaması, PDF/CSV rapor, analiz geçmişi, S&R modülleri, Model & Dataset Lab) pasif ve "Planlı" etiketlidir.

## Genişletilebilirlik

- Yeni ekran: `web/src/config/navigation.ts` + `src/app/<rota>/page.tsx`.
- S&R modülü: `web/src/features/sar-modules/registry.ts`. Lab bölümü: `web/src/features/lab/registry.ts`. Gerçek kaynak bağlanana kadar değer göstermezler.
- Gerçek API: `NEXT_PUBLIC_THERMA_API_MODE=http`; arayüz yalnızca `AnalysisService` arayüzüne bağlıdır. Codex inference sözleşmesiyle uyum ayrı PR'da ele alınacaktır.
