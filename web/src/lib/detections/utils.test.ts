import { describe, expect, it } from "vitest";
import type { Detection, FrameDetections } from "@/lib/api/contract";
import { bandOf, boxToPercent, bucketFrames, confidenceHistogram, filterByConfidence, findFrameAt, summarizeFrames } from "./utils";

const det = (id: string, confidence: number): Detection => ({
  id, classId: 0, className: "person", confidence, box: { x: 10, y: 10, width: 10, height: 20 },
});
const frame = (timestampMs: number, ...confs: number[]): FrameDetections => ({
  frameIndex: Math.round(timestampMs / 33), timestampMs, detections: confs.map((c, i) => det(`${timestampMs}-${i}`, c)),
});

describe("filterByConfidence", () => {
  it("eşik değerini dahil eder", () => {
    expect(filterByConfidence([det("a", 0.5), det("b", 0.49)], 0.5).map((d) => d.id)).toEqual(["a"]);
  });
});

describe("findFrameAt", () => {
  const frames = [frame(0), frame(200), frame(400)];
  it("zamandan önceki son kareyi döndürür", () => {
    expect(findFrameAt(frames, 350)?.timestampMs).toBe(200);
    expect(findFrameAt(frames, 400)?.timestampMs).toBe(400);
  });
  it("ilk kareden önceyse null", () => {
    expect(findFrameAt([frame(500)], 100)).toBeNull();
  });
  it("tolerans dışındaki eski kareyi göstermez", () => {
    expect(findFrameAt(frames, 5000, 1000)).toBeNull();
  });
  it("boş listede null", () => {
    expect(findFrameAt([], 0)).toBeNull();
  });
});

describe("boxToPercent", () => {
  it("piksel konumunu yüzdeye çevirir (sol-üst orijin, xywh)", () => {
    const p = boxToPercent({ x: 64, y: 51.2, width: 32, height: 25.6 }, { width: 640, height: 512 });
    expect(p.left).toBeCloseTo(10);
    expect(p.top).toBeCloseTo(10);
    expect(p.width).toBeCloseTo(5);
    expect(p.height).toBeCloseTo(5);
  });
  it("sınır dışı kutuyu kırpar", () => {
    const p = boxToPercent({ x: 630, y: 500, width: 50, height: 50 }, { width: 640, height: 512 });
    expect(p.left + p.width).toBeLessThanOrEqual(100);
    expect(p.top + p.height).toBeLessThanOrEqual(100);
  });
});

describe("confidenceHistogram", () => {
  it("1.0 değerini son bine koyar ve toplamı korur", () => {
    const bins = confidenceHistogram([det("a", 0), det("b", 0.05), det("c", 0.95), det("d", 1)], 10);
    expect(bins[0]!.count).toBe(2);
    expect(bins[9]!.count).toBe(2);
    expect(bins.reduce((s, b) => s + b.count, 0)).toBe(4);
  });
  it("NaN skorları yok sayar", () => {
    expect(confidenceHistogram([det("a", NaN)], 10).every((b) => b.count === 0)).toBe(true);
  });
});

describe("summarizeFrames", () => {
  it("eşik üstü toplam, tepe ve ortalamayı hesaplar", () => {
    const s = summarizeFrames([frame(0, 0.9, 0.3), frame(200, 0.8), frame(400)], 0.5);
    expect(s.totalDetections).toBe(2);
    expect(s.peakDetectionsPerFrame).toBe(1);
    expect(s.framesWithDetections).toBe(2);
    expect(s.meanConfidence).toBeCloseTo(0.85);
    expect(s.framesAnalyzed).toBe(3);
  });
  it("tespit yoksa ortalama null (0 değil)", () => {
    expect(summarizeFrames([frame(0)], 0.5).meanConfidence).toBeNull();
  });
});

describe("bucketFrames", () => {
  it("analiz edilmeyen kovaları sıfır tespitten ayırır", () => {
    const b = bucketFrames([frame(0, 0.9), frame(900, 0.9, 0.8)], 1000, 0.5, 10);
    expect(b[0]).toMatchObject({ analyzed: true, peak: 1 });
    expect(b[5]).toMatchObject({ analyzed: false, peak: 0 });
    expect(b[9]).toMatchObject({ analyzed: true, peak: 2 });
  });
});

describe("bandOf", () => {
  it("görsel bantları ayırır", () => {
    expect([bandOf(0.9), bandOf(0.6), bandOf(0.2)]).toEqual(["high", "medium", "low"]);
  });
});
