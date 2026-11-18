# Ortak Person inference API sözleşmesi — önerilen v1

Bu belge Claude’un Next.js çalışması ve sonraki FastAPI uygulaması için ortak sözleşmedir. Bu PR endpoint veya frontend uygulamaz. Python adaptörü `src/evaluation/inference.py` içindedir; yalnızca güvenilen, bu pipeline’dan çıkan tek sınıflı `best.pt` kullanılır. Exploratory baseline sonuçları bağımsız saha doğrulaması değildir.

## Önerilen HTTP yüzeyi

`POST /api/v1/detections`, `multipart/form-data`:

- `image`: tek JPEG/PNG dosyası.
- `confidence`: isteğe bağlı sayı, varsayılan `0.25`, aralık `[0,1]`. Kullanıcı arayüzündeki filtre değişikliği yeni bir model değerlendirmesi veya testten seçilmiş optimum eşik olarak sunulmamalıdır.

Başarılı gövde, Python adaptörünün gerçek döndürdüğü biçim:

```json
{
  "schema_version": "1.0",
  "image": {"width": 640, "height": 512},
  "detections": [
    {
      "bbox_xyxy": [64.0, 128.0, 192.0, 384.0],
      "confidence": 0.9,
      "class_id": 0,
      "class_name": "Person"
    }
  ]
}
```

Bu yalnızca **şema örneğidir**; gerçek model sonucu değildir. Tespit yoksa `detections=[]` döner; hata ile aynı anlamda değildir. Confidence kalibre edilmiş insan varlığı olasılığı olarak sunulmamalıdır. Kutular prediction’dır; ground truth değildir.

Koordinatlar **orijinal görüntünün** sürekli 0 tabanlı piksel xyxy değerleridir: sol/üst `(x1,y1)`, sağ/alt `(x2,y2)`. Normalize değildir, 640×640 letterbox koordinatı değildir. Alan pozitiftir ve kutular orijinal boyut sınırları içindedir. Next.js görselde ölçek/oran ve varsa object-fit boşluklarını hesaba katmalı, kutuyu yalnızca gösterim için dönüştürmelidir. Görüntü EXIF yönü servis girişinde tek bir tanımlı politikayla çözümlenip aynı piksel/görüntü boyutu üzerinden görüntülenmelidir; eğitim hazırlığı yönlendirilmiş EXIF girdisini reddeder.

## Python kullanımı

```python
from src.evaluation.inference import load_person_detector, predict_person

model = load_person_detector('/trusted/model-storage/best.pt')  # süreç başlangıcında bir kez
result = predict_person(model, '/local/upload.png', confidence=0.25, device='cpu')
```

GPU servisi için `device=0` seçilebilir; inference CPU’da çalışabilir, eğitim başlatmaz. Model her istekte yeniden yüklenmemelidir. Adaptör `.predict` için imgsz=640, NMS IoU=.70, max_det=300 kullanır ve JSON’da bbox/confidence/class/boyutları döndürür. Servis sürümü daha sonra run_id ve best.pt SHA256 ile model kimliğini ayrıca sağlamalı; eğitim manifesti ve değerlendirme kapsamı model kaydına bağlanmalıdır. Bu alanlar mevcut Python dönüşüne eklenmiş gibi varsayılmamalıdır.

Servis, dosyayı görüntü olarak doğrulamalı; desteklenmeyen format, bozuk görüntü ve geçersiz parametreyi açıklamalı 4xx cevaplarıyla ayırmalıdır. Önerilen limitler 10 MiB yükleme ve 25 milyon piksel; endpoint uygulanırken sabitlenip frontend’e bildirilmelidir. Model yükleme/servis hatası 5xx olmalı, boş tespit cevabı olarak gizlenmemelidir. Kullanıcıdan `.pt` yüklemesi veya sunucu dosya yolu kabul edilmez. Upload yolları response içine yazılmaz. Sunucuya özgü hata gövdesi ve zamanlama alanları endpoint PR’ında kesinleştirilecektir.

## Kapsam

Model HIT-UAV termal görüntülerinde tek sınıf Person baseline’ıdır. RGB veya WiSARD üzerinde doğrulanmış başarı iddia edilmez. Sonuç konum/rota/sıcaklık ya da kurtarma önceliği kararı değildir. Bu aşamada model API gereksinimleri belgelenmiştir; mevcut frontend kodu değiştirilmemiştir.
