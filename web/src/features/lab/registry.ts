import { Copy, FlaskConical, GitBranch, Layers3, ScanEye, Split, Target, type LucideIcon } from "lucide-react";

/**
 * Model & Dataset Lab bölüm kayıt defteri (mühendislik modülü, planlı).
 * Her bölüm, beslenmesi gereken GERÇEK kaynağı belirtir (Codex tarafının ürettiği rapor/manifest).
 * Kaynak bağlanana kadar hiçbir metrik, sayı veya grafik gösterilmez.
 */
export interface LabSection {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  source: string;
}

export const LAB_SECTIONS: readonly LabSection[] = [
  { id: "splits", title: "Train / Validation / Test dağılımı", description: "Split başına görüntü ve Person kutusu sayıları.", icon: Split, source: "Eğitim hazırlık manifesti (Notebook 04)" },
  { id: "classes", title: "Veri seti boyutu ve sınıf dağılımı", description: "Kaynak ve filtrelenmiş alt küme sayımları, dışlanan görüntüler.", icon: Layers3, source: "HIT-UAV denetim raporu (Notebook 02)" },
  { id: "duplicates", title: "Yakın benzer ve tekrar görüntüler", description: "Tam kopya ve dHash yakınlık adayları.", icon: Copy, source: "Sızıntı inceleme paketi (docs/leakage_review.md)" },
  { id: "leakage", title: "Olası veri sızıntısı incelemesi", description: "Split'ler arası aday çiftler ve manuel inceleme durumu.", icon: ScanEye, source: "Sızıntı inceleme paketi + manuel kararlar" },
  { id: "metrics", title: "Precision / Recall / mAP", description: "Ayrı test değerlendirmesi; kapsamı ve eşik politikasıyla birlikte.", icon: Target, source: "YOLO11s baseline değerlendirme kaydı" },
  { id: "errors", title: "False positive / false negative örnekleri", description: "Hata örnekleri galerisi.", icon: FlaskConical, source: "Değerlendirme tahmin dökümü" },
  { id: "runs", title: "Eğitim deneyleri ve model sürümleri", description: "Çalıştırma kimliği, ağırlık özeti, ayarlar.", icon: GitBranch, source: "Model kaydı (run_id, best.pt SHA256)" },
];
