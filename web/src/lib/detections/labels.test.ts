import { describe, expect, it } from "vitest";
import { placeLabels, type LabelInput } from "./labels";

const item = (id: string, x: number, y: number, priority: number): LabelInput => ({ id, x, y, w: 16, h: 30, lw: 70, lh: 18, priority });
const overlaps = (a: { left: number; top: number }, b: { left: number; top: number }) =>
  Math.abs(a.left - b.left) < 70 && Math.abs(a.top - b.top) < 18;

describe("placeLabels", () => {
  it("tek tespitte etiketi kutunun üstüne koyar", () => {
    const [p] = placeLabels([item("a", 100, 100, 0.9)], { width: 640, height: 512 });
    expect(p).toMatchObject({ left: 100, top: 100 - 18 - 3, displaced: false });
  });

  it("yakın iki tespitte etiketler üst üste binmez", () => {
    const out = placeLabels([item("a", 100, 100, 0.9), item("b", 120, 110, 0.8)], { width: 640, height: 512 });
    expect(overlaps(out[0]!, out[1]!)).toBe(false);
  });

  it("yüksek skorlu tespit doğal konumunu korur", () => {
    const out = placeLabels([item("low", 100, 100, 0.3), item("high", 105, 100, 0.95)], { width: 640, height: 512 });
    const high = out.find((p) => p.id === "high")!;
    expect(high.displaced).toBe(false);
    expect(high.top).toBe(100 - 18 - 3);
  });

  it("kenardaki etiketi görüntü sınırına kırpar", () => {
    const [p] = placeLabels([item("a", 630, 2, 0.9)], { width: 640, height: 512 });
    expect(p!.left + 70).toBeLessThanOrEqual(640);
    expect(p!.top).toBeGreaterThanOrEqual(0);
  });

  it("dört yoğun tespitte de çakışma yok", () => {
    const items = [item("a", 200, 200, 0.9), item("b", 215, 205, 0.85), item("c", 230, 210, 0.8), item("d", 205, 230, 0.7)];
    const out = placeLabels(items, { width: 640, height: 512 });
    for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) expect(overlaps(out[i]!, out[j]!)).toBe(false);
  });

  it("girdi sırasını korur", () => {
    const out = placeLabels([item("x", 10, 300, 0.1), item("y", 400, 300, 0.9)], { width: 640, height: 512 });
    expect(out.map((p) => p.id)).toEqual(["x", "y"]);
  });
});
