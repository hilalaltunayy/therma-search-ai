# Faz 1 teknik kararları

- **Küçük Python modülleri:** Notebook anlatım ve görselleştirme yapar; dosya okuma, kutu ayrıştırma, kalite kontrolü ve indirme ayrı modüllerdedir. Böylece Colab ile yerel testler aynı kodu kullanır.
- **Az bağımlılık:** Pillow görüntü çözme/doğrulama; Matplotlib çizim; nbformat notebook şeması; nbclient/ipykernel gerçek hücre yürütme için. JSON/XML/hash/path ve testlerde standart kütüphane kullanılır. Pandas, OpenCV, PyTorch, YOLO, RF-DETR, Claude API ve otomasyon eklenmedi.
- **Açık koordinat konvansiyonu:** COCO benzeri şema ile kutunun anlamı ayrı kararlardır. `bbox_format` zorunludur; dosya uzantısından veya README'den normalize YOLO etiketi çıkarılmaz. VOC 1 tabanlı kapalı aralık ile 0 tabanlı yarı açık aralık açıkça seçilir. Çıktı sürekli 0 tabanlı piksel xyxy'dir; kırpma, yeniden boyutlandırma ve sınıf eşleme yoktur.
- **Şema doğrulama kapısı:** Config varsayılan olarak boştur. Adaptörler genel COCO alan yapısı veya standart VOC XML içindir; bunların gerçek HIT-UAV v1.2.1 şeması olduğu henüz doğrulanmadı. Merkez tabanlı özel XML, normalize TXT veya OBB varsa gerçek örneğe dayalı ek adaptör gerekir.
- **Eksik veri sıfır değildir:** Veri yokken istatistik üretilmez. Etiket kaynağı hatasında rapor `complete=False` olur; sınıf grafiği atlanır. Boş etiket, eksik kayıt ve kayıp görüntü ayrı raporlanır. Sınıf sayıları eksik/bozuk görüntüye ait ayrıştırılmış kayıtları da kapsar; bu kapsam raporda belirtilir.
- **DontCare korunur:** Yeniden adlandırma/silme yapılmaz. Çizimde kesik kutu kullanılır. Ignore bölgesi, eğitim sınıfı veya dışlanan nesne olarak ele alınması bilimsel değerlendirme kararıdır; kullanıcı onayını bekler.
- **Özgün splitler:** Yalnızca kullanıcı tarafından doğrulanmış mevcut split kökleri analiz edilir. Rastgele yeniden bölme yoktur. Tam dosya kopyası denetimi isteğe bağlıdır ve SHA256 ek disk I/O'su açıkça belirtilir. Yakın kare/aynı uçuş/konum denetiminin yerine geçmez.
- **Test kümesi:** Şema ve dosya bütünlüğü incelenebilir; model/hiperparametre/eşik seçimi için kullanılmaz.
- **İndirmeler kapalı:** Metadata, dosya indirme ve arşiv çıkarma ayrı kullanıcı seçimleridir. ZIP dışındaki türler otomatik tahmin edilmez. Dosya boyutu ve checksum hatası tamamlanmış dosya üretmez; mevcut hedefin üzerine yazılmaz.
- **Gelecek modeller:** YOLO11s ilk adaydır; RF-DETR Small karşılaştırması daha sonra planlanacaktır. Bu aşamada eğitim, ağırlık ve model metriği yoktur.

## Açık bilimsel kararlar

Gerçek v1.2.1 şeması/koordinatları, DontCare semantiği, mevcut split üyelikleri ve çekim grupları, eksik anotasyon inceleme protokolü, WiSARD örnek sürümü ve kullanım koşulları. Bu kararlar veri incelemesinden sonra kullanıcı tarafından onaylanacak.
