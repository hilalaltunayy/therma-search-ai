# Frontend ↔ FastAPI API sözleşmesi (taslak v1)

> **Durum: ÖNERİ / TASLAK.** Bu sözleşmeyi uygulayan bir backend **henüz yoktur**. Aşağıdaki uç noktalar hiçbir sunucuda çalışmaz.
> Web arayüzü varsayılan olarak tarayıcı içi **DEMO / MOCK** servisle çalışır; mock sonuçları gerçek model tahmini değildir.
> Sözleşmenin tip karşılığı: [`web/src/lib/api/contract.ts`](../web/src/lib/api/contract.ts). Çelişki olursa bu belge esas alınır ve tip dosyası düzeltilir.
> Koordinat konvansiyonu ve sınıf eşlemesi bilimsel kararlardır ([AGENTS.md](../AGENTS.md)); aşağıdaki seçimler **kullanıcı ve AI tarafı (Codex) onayı** bekler.

## 1. Genel kurallar

| Konu | Karar |
| --- | --- |
| Temel yol | `/api/v1` — kırıcı değişiklik `v2` ile gelir |
| Biçim | JSON (`application/json`); yalnızca yükleme `multipart/form-data` |
| Alan adları | **camelCase** (FastAPI/Pydantic'te `alias_generator=to_camel`, `populate_by_name=True`) |
| Zaman | ISO-8601 UTC string (`2026-11-18T10:20:00Z`); süreler milisaniye |
| Kimlik doğrulama | Yok (yerel/prototip). Eklenirse `Authorization` başlığı; sözleşme dışı. |
| CORS | Geliştirmede `http://localhost:3000` izinli olmalı |
| Doğrulama | İstemci ön doğrulaması **kolaylıktır**; sunucu tüm kuralları yeniden doğrular |

## 2. Koordinat konvansiyonu (öneri)

Kutular **orijinal medya karesinin piksel uzayındadır** (ölçeklenmiş/letterbox kopya değil):

- Orijin **sol-üst**; `x` sağa, `y` aşağı artar.
- `box = { x, y, width, height }` — `x,y` kutunun **sol-üst köşesi**, boyutlar piksel (**xywh**, normalize değil).
- Geçerlilik: `x ≥ 0`, `y ≥ 0`, `width > 0`, `height > 0`, `x + width ≤ media.width`, `y + height ≤ media.height`.
- Açılı (rotated) kutu yok. Alt-piksel değerler (ondalık) geçerlidir.
- `media.width/height` yanıtta **her zaman** bulunur; arayüz kutuları buna göre ölçekler. YOLO'nun letterbox/normalize çıktısı backend tarafında orijinal piksel uzayına çevrilmelidir.

Gerekçe: Notebook 02'deki HIT-UAV adaptörü piksel `xywh` kullanır; arayüz DOM yüzdesine çevirmek için orijinal boyut ister. `src/lib/api/guards.ts` sınır dışı kutuları **çizmeden reddeder** (konvansiyon ihlalini sessizce göstermemek için).

## 3. Sınıflar

`Detection.classId` / `className` modelin sınıf kimliğidir. Eşleme `ModelInfo.classes` içinde bildirilir ve **AI tarafına aittir**; arayüz sınıf kimliği varsaymaz. DontCare'in çıktıda yer alıp almayacağı ayrı bir bilimsel karardır (AGENTS.md) ve burada **verilmemiştir**; MVP arayüzü yalnızca gelen sınıfları listeler.

## 4. Yükleme sınırları (öneri)

Gerçek değerler `GET /capabilities` ile bildirilir; arayüz yanıt gelene kadar bu varsayılanları kullanır.

| Tür | MIME | Azami boyut | Ek |
| --- | --- | --- | --- |
| Görüntü | `image/jpeg`, `image/png`, `image/webp` | 20 MB | TIFF/radyometrik formatlar tarayıcıda önizlenemediği için bu sürümde yok |
| Video | `video/mp4`, `video/webm`, `video/quicktime` | 500 MB | azami süre 600 sn; codec çözülemezse `media_decode_failed` |

Tek istekte tek dosya. Uzantı MIME'ı yanıltabilir; sunucu içeriği (magic bytes) doğrulamalıdır.

## 5. Uç noktalar

| Metot ve yol | Amaç | Başarılı yanıt |
| --- | --- | --- |
| `GET /api/v1/health` | Servis/model durumu | `200` `ServiceHealth` |
| `GET /api/v1/capabilities` | Sürüm, model, yükleme limitleri | `200` `Capabilities` |
| `POST /api/v1/analyses/image` | Görüntü analizi işi oluştur | `202` `Job` |
| `POST /api/v1/analyses/video` | Video analizi işi oluştur | `202` `Job` |
| `GET /api/v1/jobs/{id}` | İş durumu/ilerleme | `200` `Job` |
| `GET /api/v1/jobs/{id}/result` | Tespit sonuçları | `200` `AnalysisResult` · iş bitmediyse `409 job_not_ready` |
| `DELETE /api/v1/jobs/{id}` | Çalışan işi iptal et | `200` `Job` (`canceled`) |

**Yükleme isteği:** `multipart/form-data`; alanlar `file` (zorunlu) ve `options` (JSON string, isteğe bağlı):

```json
{ "minConfidence": 0.1, "frameStride": 1 }
```

- `minConfidence` (0–1, varsayılan 0.1): sunucu bunun altındaki tespitleri **döndürmez**. Arayüzün eşik kaydırıcısı yalnızca bunun üzerinde süzer; yanıttaki `minConfidenceApplied` uygulanan değerdir.
- `frameStride` (≥1, yalnızca video, varsayılan 1): her N. kare analiz edilir.

Görüntü işleri de aynı iş modelini kullanır (arayüz tek akışla çalışsın diye); hızlı tamamlanması beklenir.

## 6. Şemalar (özet)

```jsonc
// Job
{ "id": "…", "kind": "image|video", "status": "queued|running|succeeded|failed|canceled",
  "provenance": "mock|model",
  "progress": { "processedFrames": 12, "totalFrames": 120 /*veya null*/, "ratio": 0.1 /*veya null*/ },
  "createdAt": "…", "startedAt": "…|null", "finishedAt": "…|null",
  "error": null /* failed ise ApiError */, "resultAvailable": false }

// AnalysisResult
{ "jobId": "…", "provenance": "mock|model",
  "model": { "name": "yolo11s", "version": "…|null", "classes": [{ "id": 0, "name": "person" }] },
  "media": { "kind": "video", "width": 640, "height": 512, "durationMs": 6000, "fps": 30, "totalFrames": 180 },
  "frames": [ { "frameIndex": 0, "timestampMs": 0,
      "detections": [ { "id": "0-0", "classId": 0, "className": "person", "confidence": 0.87,
                        "box": { "x": 120.5, "y": 80, "width": 14, "height": 24 } } ] } ],
  "minConfidenceApplied": 0.1, "frameStride": 1,
  "timing": { "processingMs": 4210, "measured": true }, "createdAt": "…" }
```

- `frames` zaman sırasındadır (artan `timestampMs`); görüntüde tek elemandır (`frameIndex 0`, `timestampMs 0`). Tespiti olmayan analiz edilmiş kare boş `detections` ile **listelenir** (arayüz "analiz edilmedi" ile "sıfır tespit"i ayırır).
- `Detection.id` sonuç içinde benzersizdir; **izleme (tracking) kimliği değildir**. Video toplamı bu yüzden "benzersiz kişi sayısı" değil, "kare toplamı"dır.
- `confidence` model skorudur; kalibre olasılık varsayılmaz.
- `provenance: "mock"` olan her yanıt arayüzde **DEMO / MOCK DATA** olarak etiketlenir. Gerçek backend `"model"` döndürmeli ve `timing.measured=true` olmalıdır.
- İsteğe bağlı gelecek alan: `processedMediaUrl` (sunucuda render edilmiş video). MVP arayüzü kutuları istemcide çizer.

## 7. Video işleme durumları

```text
queued → running → succeeded
              ├──→ failed      (error dolu)
queued/running ──→ canceled    (DELETE /jobs/{id})
```

`succeeded`, `failed`, `canceled` **terminaldir**. `resultAvailable` yalnızca `succeeded` iken `true`. İstemci `GET /jobs/{id}` ile ~500 ms aralıkla yoklar (SSE/WebSocket bu sürümde yok). Ardışık 3 yoklama hatasında iş arayüzde başarısız sayılır.

## 8. Hatalar

Her 4xx/5xx yanıt gövdesi:

```json
{ "error": { "code": "file_too_large", "message": "…", "retryable": false, "details": { "maxBytes": 524288000 } } }
```

| Kod | HTTP | Tekrar denenebilir |
| --- | --- | --- |
| `invalid_request` | 400/422 | hayır |
| `unsupported_media_type` | 415 | hayır |
| `file_too_large` | 413 | hayır |
| `media_decode_failed` | 422 | hayır |
| `video_too_long` | 422 | hayır |
| `job_not_found` | 404 | hayır |
| `job_not_ready` | 409 | evet |
| `model_unavailable` | 503 | evet |
| `inference_failed` | (iş `failed`) | genelde evet |
| `rate_limited` | 429 | evet |
| `internal_error` | 500 | duruma bağlı |

Yalnızca istemcide üretilenler: `network_error`, `timeout`, `invalid_response`, `aborted`. Bozuk/sözleşme dışı yanıt `invalid_response` olur; arayüz uydurma sonuç göstermez.

## 9. Mock ile gerçek servis ayrımı

| | Mock (`web/src/lib/api/mock-service.ts`) | HTTP istemcisi (`http-client.ts`) |
| --- | --- | --- |
| Seçim | varsayılan | `NEXT_PUBLIC_THERMA_API_MODE=http` |
| Veri | tohumlu **yapay** kutular, model yok | backend yanıtı |
| Süre | simülasyon (`measured:false`) | backend ölçümü |
| Durum | çalışır (tarayıcı içi) | **gerçek sunucuya karşı denenmedi**; yalnızca sahte `fetch` ile birim test |

İkisi aynı `AnalysisService` arayüzünü uygular; seçim `web/src/lib/api/index.ts` içinde tek yerdedir.

## 10. Açık kararlar (Codex / kullanıcı onayı)

1. Piksel **xywh sol-üst** konvansiyonu onaylanacak mı (bkz. §2)?
2. Sınıf listesi ve DontCare'in çıktıdaki yeri.
3. Yükleme limitleri ve video süre sınırı (GPU/maliyet ve Colab deneyimine göre).
4. Varsayılan `minConfidence` ve değerlendirme protokolü ile ilişkisi (arayüzdeki 0.25 yalnızca görüntüleme varsayılanıdır).
5. Yoklama yerine SSE; işlenmiş video çıktısı; kalıcı analiz geçmişi (`GET /api/v1/jobs`).
6. WiSARD RGB/termal çiftleri için istek şeması (şimdilik yalnızca tek termal akış).
