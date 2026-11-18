import { BarChart3, Crosshair, Radar, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
  /** "planned": henüz işlevsel değil; sidebar'da etiketle gösterilir. */
  status: "available" | "planned";
}

/** Yeni ekranlar yalnızca bu listeye eklenir; sidebar ve üst başlık bu kaynaktan beslenir. */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/workspace", label: "Detection Workspace", description: "Yükle, analiz et, incele", icon: Crosshair, status: "available" },
  { href: "/analytics", label: "Detection Analytics", description: "Sayılar, dağılım, zaman çizelgesi", icon: BarChart3, status: "available" },
  { href: "/operations", label: "Search & Rescue", description: "Öncelik, bölge, rota, ekipler", icon: Radar, status: "planned" },
];
