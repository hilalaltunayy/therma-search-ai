import { BarChart3, Crosshair, FlaskConical, Radar, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
  /** "planned": henüz işlevsel değil; rayda kilitli/soluk ve "Planlı" etiketiyle gösterilir. */
  status: "available" | "planned";
}

/** Yeni ekranlar yalnızca bu listeye eklenir; ray, genişletilmiş menü ve üst başlık bu kaynaktan beslenir. */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/workspace", label: "Detection Workspace", description: "Yükle, analiz et, incele", icon: Crosshair, status: "available" },
  { href: "/analytics", label: "Detection Analytics", description: "Sayılar, dağılım, zaman çizelgesi", icon: BarChart3, status: "available" },
  { href: "/operations", label: "Search & Rescue", description: "Öncelik, bölge, rota, ekipler", icon: Radar, status: "planned" },
  { href: "/lab", label: "Model & Dataset Lab", description: "Veri seti ve model değerlendirmesi", icon: FlaskConical, status: "planned" },
];
