import type { BoundingBox, Detection, FrameDetections, MediaInfo } from "@/lib/api/contract";

/** Skor bandı yalnızca GÖRSEL sınıflandırmadır; kalibre edilmiş güvenilirlik iddiası taşımaz. */
export type ConfidenceBand = "high" | "medium" | "low";

export function bandOf(confidence: number): ConfidenceBand {
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

export function filterByConfidence<T extends { confidence: number }>(items: readonly T[], threshold: number): T[] {
  return items.filter((d) => d.confidence >= threshold);
}

/**
 * Zaman damgasından (ms) görüntülenecek kareyi bulur: `timestampMs ≤ timeMs` koşulunu sağlayan son kare.
 * Kare, `maxGapMs` içinde değilse (örn. analiz edilmeyen aralık) null döner — eski kutular gösterilmez.
 * `frames` artan sırada olmalıdır.
 */
export function findFrameAt(
  frames: readonly FrameDetections[],
  timeMs: number,
  maxGapMs = 1000,
): FrameDetections | null {
  if (frames.length === 0) return null;
  let lo = 0;
  let hi = frames.length - 1;
  let best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const frame = frames[mid]!;
    if (frame.timestampMs <= timeMs) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  if (best < 0) return null;
  const found = frames[best]!;
  return timeMs - found.timestampMs <= maxGapMs ? found : null;
}

export interface PercentBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Piksel uzayındaki kutuyu medya boyutuna göre yüzde konuma çevirir (0–100, sınırlara kırpılır). */
export function boxToPercent(box: BoundingBox, media: Pick<MediaInfo, "width" | "height">): PercentBox {
  const clamp = (v: number) => Math.min(100, Math.max(0, v));
  const left = clamp((box.x / media.width) * 100);
  const top = clamp((box.y / media.height) * 100);
  const right = clamp(((box.x + box.width) / media.width) * 100);
  const bottom = clamp(((box.y + box.height) / media.height) * 100);
  return { left, top, width: right - left, height: bottom - top };
}

export interface HistogramBin {
  /** Alt sınır (dahil). */
  from: number;
  /** Üst sınır (son bin hariç dışlayıcı; son bin için 1.0 dahil). */
  to: number;
  count: number;
}

/** [0,1] aralığını `binCount` eşit parçaya böler. confidence = 1 son bine dahildir. */
export function confidenceHistogram(detections: readonly Pick<Detection, "confidence">[], binCount = 10): HistogramBin[] {
  const bins: HistogramBin[] = Array.from({ length: binCount }, (_, i) => ({
    from: i / binCount,
    to: (i + 1) / binCount,
    count: 0,
  }));
  for (const d of detections) {
    if (!Number.isFinite(d.confidence)) continue;
    const idx = Math.min(binCount - 1, Math.max(0, Math.floor(d.confidence * binCount)));
    bins[idx]!.count += 1;
  }
  return bins;
}

export interface DetectionSummary {
  framesAnalyzed: number;
  framesWithDetections: number;
  /** Eşik üstü toplam tespit (kare toplamı). Benzersiz kişi sayısı DEĞİLDİR: izleme yapılmaz. */
  totalDetections: number;
  /** Tek karedeki en yüksek eşik üstü tespit sayısı. */
  peakDetectionsPerFrame: number;
  meanConfidence: number | null;
  minConfidence: number | null;
  maxConfidence: number | null;
}

export function summarizeFrames(frames: readonly FrameDetections[], threshold: number): DetectionSummary {
  let total = 0;
  let peak = 0;
  let withDet = 0;
  let sum = 0;
  let min: number | null = null;
  let max: number | null = null;
  for (const frame of frames) {
    const kept = filterByConfidence(frame.detections, threshold);
    total += kept.length;
    peak = Math.max(peak, kept.length);
    if (kept.length > 0) withDet += 1;
    for (const d of kept) {
      sum += d.confidence;
      min = min === null ? d.confidence : Math.min(min, d.confidence);
      max = max === null ? d.confidence : Math.max(max, d.confidence);
    }
  }
  return {
    framesAnalyzed: frames.length,
    framesWithDetections: withDet,
    totalDetections: total,
    peakDetectionsPerFrame: peak,
    meanConfidence: total > 0 ? sum / total : null,
    minConfidence: min,
    maxConfidence: max,
  };
}

export function allDetections(frames: readonly FrameDetections[]): Detection[] {
  return frames.flatMap((f) => f.detections);
}

export interface TimelineBucket {
  startMs: number;
  endMs: number;
  /** Kova içindeki en yüksek eşik üstü kare başına tespit sayısı. */
  peak: number;
  /** Kovada analiz edilen kare var mı? (yoksa "veri yok" ile "sıfır tespit" ayrılır.) */
  analyzed: boolean;
}

/** Zaman çizelgesi için kareleri en fazla `bucketCount` kovaya indirger. */
export function bucketFrames(
  frames: readonly FrameDetections[],
  durationMs: number,
  threshold: number,
  bucketCount = 120,
): TimelineBucket[] {
  const span = Math.max(durationMs, 1);
  const n = Math.max(1, bucketCount);
  const buckets: TimelineBucket[] = Array.from({ length: n }, (_, i) => ({
    startMs: (i / n) * span,
    endMs: ((i + 1) / n) * span,
    peak: 0,
    analyzed: false,
  }));
  for (const frame of frames) {
    const idx = Math.min(n - 1, Math.max(0, Math.floor((frame.timestampMs / span) * n)));
    const b = buckets[idx]!;
    b.analyzed = true;
    b.peak = Math.max(b.peak, filterByConfidence(frame.detections, threshold).length);
  }
  return buckets;
}
