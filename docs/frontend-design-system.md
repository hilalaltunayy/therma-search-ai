# Therma Search AI — web tasarım sistemi (v0.1)

Amaç: arama-kurtarma operasyon/İHA görüntü analiz merkezinde kullanılabilecek, ciddi ve sade bir **premium dark** arayüz. Token'lar tek kaynaktan gelir: [`web/src/app/globals.css`](../web/src/app/globals.css) (`@theme`).

> Not: Tasarım referans görselleri bu sürümün geliştirilmesi sırasında elimde yoktu; palet ve yerleşim, görev tanımındaki yazılı yönerge (koyu lacivert/slate, cyan/teal vurgu, amber uyarı, ince çerçeveler) esas alınarak kuruldu. Görseller paylaşıldığında token değerleri tek dosyada ayarlanabilir.

## Renk

| Rol | Token | Değer | Kullanım |
| --- | --- | --- | --- |
| Zemin | `base` | `#060a13` | sayfa zemini |
| Yüzey | `surface` / `raised` / `overlay` | `#0a111d` / `#0f1828` / `#152136` | panel → yükseltilmiş → seçili/hover |
| Çizgi | `line` / `line-strong` | `#1c2a40` / `#2a3b57` | 1 px çerçeve, ayırıcı |
| Metin | `ink` / `muted` / `subtle` | `#e8eef8` / `#9aa9c0` / `#8393ab` | birincil / ikincil / üçüncül (yüzeyler üzerinde AA hedefi) |
| Vurgu | `accent` (cyan) `#22d3ee`, `teal` `#2dd4bf`, `electric` `#4f8cff` | | birincil eylem, yüksek skor / orta skor |
| Durum | `warn` `#f59e0b`, `danger` `#fb5a6e`, `ok` `#34d399` (+ `-soft` zeminler) | | DEMO/uyarı, hata, başarı |

Kurallar: vurgu rengi **seyrek** kullanılır (birincil eylem, seçili durum, veri); **amber yalnızca** DEMO/MOCK ve uyarı içindir; kırmızı yalnızca hata.
Skor bantları (≥0.75 cyan, ≥0.5 mavi, altı amber) yalnızca **görsel** sınıflandırmadır; kalibre güven iddiası değildir.

## Tipografi

Sistem yazı tipi yığını (`ui-sans-serif, system-ui, …`) — ağ bağımlılığı ve yazı tipi indirmesi yok; sayılar `tabular-nums`, kimlik/koordinatlar `ui-monospace`. Ölçek: etiket 10–11 px (büyük harf, geniş aralık), gövde 13 px, panel başlığı 13 px semibold, metrik 24 px semibold, sayfa başlığı 14 px.

## Aralık, şekil, derinlik

4 px tabanlı Tailwind ölçeği; panel iç boşluğu 16 px, sütun aralığı 16 px. Panel yarıçapı 12 px, düğme 8 px, rozet 6 px. Derinlik gölgeden çok **yüzey rengi + ince çerçeve** ile verilir.

## Bileşen hiyerarşisi

```text
app/layout.tsx → AnalysisProvider (durum) → AppShell (sidebar · üst çubuk · drawer)
  └─ sayfa (workspace | analytics | operations)
      ├─ ui/primitives: Panel, Badge, StatusDot, Button, Switch, Segmented, Stat, ProgressBar, StateView, DemoBadge
      ├─ workspace/*: MediaStage ▸ (UploadDropzone | <img>/<video> + DetectionOverlay + CompareHandle + durum katmanları)
      │               PlayerControls, ControlsPanel, JobPanel, DetectionList, MetricsStrip
      └─ analytics/*: ConfidenceHistogram, FrameTimeline
```

- **Panel** tüm yüzeylerin birimidir (başlık satırı + gövde); ad hoc kart yoktur.
- Veri/mantık UI'dan ayrıdır: `lib/detections` (saf fonksiyonlar), `lib/api` (sözleşme, mock, HTTP), `state/analysis-store` (yaşam döngüsü).
- **Overlay katmanı** medyadan bağımsızdır: piksel kutuları yüzdeye çevrilir; medya hangi boyutta olursa olsun hizalı kalır.

## Ekran yerleşimi

Masaüstü: sol sabit sidebar (256 px) · sticky üst çubuk (sayfa başlığı, DEMO rozeti, backend durumu) · içerik `max 1600 px`. Detection Workspace: **geniş izleme alanı** (sol, esnek) + **340 px denetim sütunu** (iş durumu, görünüm/eşik, tespit listesi); izleme alanının altında oynatıcı ve zaman çizelgesi, onun altında özet. `<lg`: sidebar çekmeceye (drawer) döner, sütunlar alt alta dizilir.

## Durumlar

| Durum | Gösterim |
| --- | --- |
| Boş | Sürükle-bırak yükleme alanı, limitler görünür |
| Doğrulama hatası | Yükleme alanında `role="alert"` mesajı (dosya kaldırılmaz) |
| Hazır | Önizleme + "Analizi başlat" |
| Yükleniyor/İşleniyor | Medya üstünde ilerleme kartı, tarama animasyonu, iptal |
| Başarılı | Kutular, özet, liste, zaman çizelgesi |
| Hata / İptal | Medya üstünde mesaj + hata kodu + yeniden dene |

DEMO/MOCK sonucu her ekranda **amber rozet** taşır (üst çubuk, izleme alanı, özet, analitik).

## Hareket ve erişilebilirlik

Mikro animasyon: panel girişinde 6 px yükselme (350 ms), durum noktası nabzı, işlem sırasında tarama çizgisi. `prefers-reduced-motion` ile tümü devre dışı kalır. Odak halkası cyan; tüm kontroller klavyeyle kullanılabilir (drawer `Esc`, karşılaştırma ayırıcısı `←/→/Home/End`, zaman çizelgesi `←/→`); "İçeriğe geç" bağlantısı; histogram için ekran okuyucu tablosu; ilerleme çubuğu `role="progressbar"`.

## Genişletilebilirlik

- Yeni ekran: `web/src/config/navigation.ts` listesine giriş + `src/app/<rota>/page.tsx`.
- Yeni SAR modülü: `web/src/features/sar-modules/registry.ts`; modül gerçek veriye bağlanana kadar `planned` kalır ve değer göstermez.
- Gerçek API: `NEXT_PUBLIC_THERMA_API_MODE=http`; UI yalnızca `AnalysisService` arayüzüne bağlıdır.
