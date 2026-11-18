import {
  ApiRequestError,
  type AnalysisResult,
  type ApiError,
  type ApiErrorEnvelope,
  type Job,
} from "./contract";

const JOB_STATUSES = ["queued", "running", "succeeded", "failed", "canceled"];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function isApiErrorEnvelope(v: unknown): v is ApiErrorEnvelope {
  return (
    isRecord(v) &&
    isRecord(v.error) &&
    typeof v.error.code === "string" &&
    typeof v.error.message === "string" &&
    typeof v.error.retryable === "boolean"
  );
}

function invalid(message: string): ApiRequestError {
  const error: ApiError = { code: "invalid_response", message, retryable: false };
  return new ApiRequestError(error);
}

/** Backend yanıtının şekil ve temel değer kontrolü (sürüm kayması ve bozuk yanıtı erken yakalar). */
export function assertJob(v: unknown): Job {
  if (!isRecord(v) || typeof v.id !== "string" || typeof v.status !== "string" || !JOB_STATUSES.includes(v.status)) {
    throw invalid("Geçersiz iş (job) yanıtı.");
  }
  if (!isRecord(v.progress)) throw invalid("İş yanıtında progress yok.");
  return v as unknown as Job;
}

/**
 * Sonuç doğrulaması: kutuların medya sınırları içinde olduğunu, skorların 0–1 arasında olduğunu
 * ve karelerin zaman sırasında olduğunu denetler. Koordinat konvansiyonu ihlali sessizce çizilmez.
 */
export function assertAnalysisResult(v: unknown): AnalysisResult {
  if (!isRecord(v) || !isRecord(v.media) || !Array.isArray(v.frames) || !isRecord(v.model)) {
    throw invalid("Geçersiz analiz sonucu yanıtı.");
  }
  const { width, height } = v.media as { width?: unknown; height?: unknown };
  if (typeof width !== "number" || typeof height !== "number" || width <= 0 || height <= 0) {
    throw invalid("Sonuçta medya boyutu eksik veya geçersiz.");
  }
  let prev = -Infinity;
  for (const frame of v.frames as unknown[]) {
    if (!isRecord(frame) || typeof frame.timestampMs !== "number" || !Array.isArray(frame.detections)) {
      throw invalid("Geçersiz kare kaydı.");
    }
    if (frame.timestampMs < prev) throw invalid("Kareler zaman sırasında değil.");
    prev = frame.timestampMs;
    for (const d of frame.detections as unknown[]) {
      if (!isRecord(d) || !isRecord(d.box) || typeof d.confidence !== "number") throw invalid("Geçersiz tespit kaydı.");
      const { x, y, width: w, height: h } = d.box as Record<string, unknown>;
      if (![x, y, w, h].every((n) => typeof n === "number" && Number.isFinite(n))) throw invalid("Kutu sayısal değil.");
      const [bx, by, bw, bh] = [x, y, w, h] as number[];
      const eps = 0.5; // yuvarlama toleransı (piksel)
      if (bw! <= 0 || bh! <= 0 || bx! < -eps || by! < -eps || bx! + bw! > width + eps || by! + bh! > height + eps) {
        throw invalid("Kutu, medya piksel sınırlarının dışında (koordinat konvansiyonu ihlali).");
      }
      if (d.confidence < 0 || d.confidence > 1) throw invalid("Skor 0–1 aralığının dışında.");
    }
  }
  return v as unknown as AnalysisResult;
}
