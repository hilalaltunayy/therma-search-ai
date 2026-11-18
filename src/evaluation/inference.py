"""Backend’den bağımsız inference sözleşmesi; import sırasında model/ağırlık yüklemez."""
import math
from pathlib import Path


def load_person_detector(weights):
    """Uygulama başlangıcında bir kez yükleyin; kullanıcıdan ağırlık dosyası kabul etmeyin."""
    path = Path(weights)
    if not path.is_file() or path.suffix != '.pt':
        raise ValueError('Yerel, güvenilen best.pt ağırlık dosyası gerekli.')
    from ultralytics import YOLO
    model = YOLO(str(path), task='detect')
    if model.names != {0: 'Person'}:
        raise ValueError('Tek sınıflı Person modeli gerekli; yanlış checkpoint.')
    return model


def serialize_person_result(result):
    """Orijinal boyuttaki piksel xyxy ve confidence; framework tensor’lerini JSON’a çevirir."""
    height, width = map(int, result.orig_shape)
    if width <= 0 or height <= 0 or result.names != {0: 'Person'}:
        raise ValueError('Model sınıf sözlüğü veya görüntü boyutu geçersiz.')
    detections = []
    if result.boxes is not None:
        boxes = result.boxes.xyxy.cpu().tolist()
        scores = result.boxes.conf.cpu().tolist()
        classes = result.boxes.cls.cpu().tolist()
        if len(boxes) != len(scores) or len(scores) != len(classes):
            raise ValueError('Tahmin tensör boyutları uyuşmuyor.')
        for box, score, category in zip(boxes, scores, classes):
            x1, y1, x2, y2 = map(float, box)
            if category != 0 or not all(math.isfinite(v) for v in (*box, score)) or not 0 <= score <= 1:
                raise ValueError('Geçersiz tahmin çıktısı.')
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise ValueError('Tahmin orijinal görüntü sınırlarının dışında.')
            detections.append({'bbox_xyxy': [x1, y1, x2, y2], 'confidence': float(score),
                               'class_id': 0, 'class_name': 'Person'})
    return {'schema_version': '1.0', 'image': {'width': width, 'height': height}, 'detections': detections}


def predict_person(model, image, *, confidence=.25, imgsz=640, device='cpu'):
    """image: yerel yol, PIL image veya ndarray; RGB/termal moduna yeni semantik yüklemez.

    FastAPI süreç başına modeli yeniden kullanabilir. Eğitim başlamaz; CPU inference
    mümkündür. Varsayılan confidence eğitim öncesi belirlenmiştir, testten seçilmez.
    """
    if not 0 <= confidence <= 1 or type(imgsz) is not int or imgsz <= 0:
        raise ValueError('Geçersiz confidence/imgsz.')
    result = model.predict(source=image, conf=confidence, imgsz=imgsz, device=device,
                           iou=.7, max_det=300, verbose=False, save=False)[0]
    return serialize_person_result(result)
