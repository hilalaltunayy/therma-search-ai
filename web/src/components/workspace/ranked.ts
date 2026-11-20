import type { Detection } from "@/lib/api/contract";

/** Kare içi sıra (#1 = en yüksek skor). İzleme kimliği DEĞİLDİR; kareler arasında değişebilir. */
export interface RankedDetection {
  detection: Detection;
  rank: number;
}

export function rankDetections(detections: readonly Detection[]): RankedDetection[] {
  return [...detections].sort((a, b) => b.confidence - a.confidence).map((detection, i) => ({ detection, rank: i + 1 }));
}
