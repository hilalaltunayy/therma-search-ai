export type ViewMode = "overlay" | "original" | "split";

/** Yalnızca görünüm tercihleri; veri değildir ve kaynağı/sonucu değiştirmez. */
export interface ViewPrefs {
  mode: ViewMode;
  showBoxes: boolean;
  showLabels: boolean;
  hiddenClasses: ReadonlySet<number>;
  /** Split modunda orijinalin kapladığı yüzde (0–100). */
  splitPct: number;
}

export const DEFAULT_VIEW_PREFS: ViewPrefs = {
  mode: "overlay",
  showBoxes: true,
  showLabels: true,
  hiddenClasses: new Set(),
  splitPct: 50,
};
