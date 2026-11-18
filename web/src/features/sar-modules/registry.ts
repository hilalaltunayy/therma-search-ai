import { Compass, Flame, MapPinned, Route, ShieldAlert, Users, type LucideIcon } from "lucide-react";

/**
 * Search & Rescue modül kayıt defteri (ikinci dönem). Her modül, hangi GERÇEK verinin bağlanması
 * gerektiğini belirtir. Veri yoksa modül "planned" kalır ve hiçbir değer üretmez/gösterilmez.
 * Yeni modül eklemek: bu listeye giriş ekle → /operations kartı otomatik oluşur;
 * işlevsel olunca `status` "available" olur ve kendi rotası (src/app/operations/<id>) eklenir.
 */
export interface SarModule {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  status: "planned";
  /** Modülün çalışması için gereken gerçek veri/sözleşme ögeleri. */
  requires: string[];
}

export const SAR_MODULES: readonly SarModule[] = [
  { id: "priority-map", title: "Arama önceliği haritası", description: "Tespit yoğunluğu ve risk puanlarından türetilen öncelik katmanı.", icon: Flame, status: "planned", requires: ["Coğrafi konumlu tespitler", "Doğrulanmış risk modeli", "Harita sağlayıcısı kararı"] },
  { id: "zones", title: "Operasyon bölgeleri", description: "Arama sektörlerinin tanımı, durumu ve kapsama takibi.", icon: MapPinned, status: "planned", requires: ["Bölge geometrisi (GeoJSON)", "Operasyon veri modeli"] },
  { id: "gps", title: "GPS koordinatları", description: "Kare/kutu → coğrafi koordinat dönüşümü.", icon: Compass, status: "planned", requires: ["İHA telemetrisi (konum, irtifa, yönelim)", "Kamera kalibrasyonu", "Koordinat sistemi kararı"] },
  { id: "risk", title: "Risk ve öncelik puanları", description: "Tespit güveni, bağlam ve arazi verisinden bileşik puan.", icon: ShieldAlert, status: "planned", requires: ["Bilimsel olarak doğrulanmış puanlama yöntemi", "Değerlendirme protokolü (kullanıcı onayı)"] },
  { id: "routes", title: "Rota planlama", description: "Ekipler için erişilebilir rota önerileri.", icon: Route, status: "planned", requires: ["Arazi/erişilebilirlik verisi", "Rota motoru seçimi"] },
  { id: "teams", title: "Görevli ekipler", description: "Ekip atama, konum ve durum izleme.", icon: Users, status: "planned", requires: ["Ekip/kimlik veri modeli", "Gizlilik ve erişim politikası"] },
];
