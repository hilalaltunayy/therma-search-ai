/**
 * Skor etiketi yerleşimi — çakışmayı önleyen açgözlü (greedy) yerleştirme.
 *
 * Girdi: ekran pikseli cinsinden kutular (görüntülenen kare içinde) ve tahmini etiket boyutları.
 * Çıktı: her etiket için sol-üst konum (piksel, kareye göre). Kutular DEĞİŞMEZ; yalnızca etiket
 * konumu seçilir. Öncelik yüksek skorlu tespitlerdedir. Hiçbir aday boş değilse en az çakışan seçilir.
 */

export interface LabelInput {
  id: string;
  /** Kutu, ekran pikseli. */
  x: number;
  y: number;
  w: number;
  h: number;
  /** Etiket boyutu, ekran pikseli. */
  lw: number;
  lh: number;
  /** Yüksek öncelik önce yerleşir (ör. confidence). */
  priority: number;
}

export interface LabelPlacement {
  id: string;
  left: number;
  top: number;
  /** Etiket kutunun dışında, üstünde/altında değilse (yığılmış) true. */
  displaced: boolean;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

function overlapArea(a: Rect, b: Rect): number {
  const ox = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
  const oy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  return ox * oy;
}

const GAP = 3;

export function placeLabels(items: readonly LabelInput[], bounds: { width: number; height: number }): LabelPlacement[] {
  const order = [...items].sort((a, b) => b.priority - a.priority);
  const placed: Rect[] = [];
  const result = new Map<string, LabelPlacement>();
  const clampX = (x: number, w: number) => Math.min(Math.max(0, x), Math.max(0, bounds.width - w));
  const clampY = (y: number, h: number) => Math.min(Math.max(0, y), Math.max(0, bounds.height - h));

  for (const it of order) {
    const above = it.y - it.lh - GAP;
    const below = it.y + it.h + GAP;
    const leftAligned = it.x;
    const rightAligned = it.x + it.w - it.lw;
    const candidates: Array<{ x: number; y: number; displaced: boolean }> = [
      { x: leftAligned, y: above, displaced: false },
      { x: rightAligned, y: above, displaced: false },
      { x: leftAligned, y: below, displaced: false },
      { x: rightAligned, y: below, displaced: false },
    ];
    // Yığılmış adaylar: kutunun üstünde/altında kademeli kaydırma.
    for (let k = 1; k <= 3; k++) {
      candidates.push({ x: leftAligned, y: above - k * (it.lh + GAP), displaced: true });
      candidates.push({ x: leftAligned, y: below + k * (it.lh + GAP), displaced: true });
    }
    // Diğer kutular da engeldir: etiket başka bir kişinin kutusunu kapatmasın.
    const otherBoxes: Rect[] = items.filter((o) => o.id !== it.id).map((o) => ({ x: o.x, y: o.y, w: o.w, h: o.h }));

    let best: { x: number; y: number; displaced: boolean; cost: number } | null = null;
    for (const c of candidates) {
      const r: Rect = { x: clampX(c.x, it.lw), y: clampY(c.y, it.lh), w: it.lw, h: it.lh };
      const ownBox: Rect = { x: it.x, y: it.y, w: it.w, h: it.h };
      let cost = 0;
      for (const p of placed) cost += overlapArea(r, p) * 4;
      for (const b of otherBoxes) cost += overlapArea(r, b) * 2;
      cost += overlapArea(r, ownBox) * 0.5; // kırpma nedeniyle kendi kutusuna binmesi daha az kötü
      if (c.displaced) cost += 1; // eşitlikte doğal konumu tercih et
      if (!best || cost < best.cost) best = { x: r.x, y: r.y, displaced: c.displaced, cost };
      if (cost === 0) break;
    }
    const b = best!;
    placed.push({ x: b.x, y: b.y, w: it.lw, h: it.lh });
    result.set(it.id, { id: it.id, left: b.x, top: b.y, displaced: b.displaced });
  }
  return items.map((it) => result.get(it.id)!);
}

/** Tek aralıklı (monospace) etiket genişliği tahmini; ölçüm yerine deterministik ve test edilebilir. */
export function estimateLabelWidth(text: string, charPx = 7, paddingPx = 12): number {
  return Math.ceil(text.length * charPx + paddingPx);
}
