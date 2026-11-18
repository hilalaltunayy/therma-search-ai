/**
 * Therma Search AI — frontend ↔ FastAPI API sözleşmesi (taslak, sürüm v1).
 *
 * Bu dosya `docs/api-contract.md` ile birlikte okunmalıdır; ikisi uyumsuz kalırsa belge esas alınır.
 * Backend henüz YOKTUR: burada tanımlanan uç noktalar hiçbir sunucuda çalışmaz. Sözleşme, AI/backend
 * tarafıyla (Codex) üzerinde anlaşılana kadar *öneridir*.
 *
 * KOORDİNAT KONVANSİYONU (öneri — bilimsel koordinat kararı kullanıcı onayına tabidir):
 *   - Kutular ORİJİNAL medya karesinin piksel uzayındadır (ölçeklenmiş/letterbox kopya değil).
 *   - Orijin sol-üst; x sağa, y aşağı artar.
 *   - `x`,`y` = kutunun sol-üst köşesi; `width`,`height` = piksel boyutu (xywh). Normalize değildir.
 *   - Geçerli kutu: 0 ≤ x, 0 ≤ y, width > 0, height > 0, x+width ≤ media.width, y+height ≤ media.height.
 *   - Açılı (rotated) kutu yoktur.
 */

export const API_VERSION = "v1" as const;

/** Sonucun kaynağı. `mock` değerleri ASLA gerçek model tahmini gibi sunulmamalıdır. */
export type Provenance = "mock" | "model";

export interface BoundingBox {
  /** Sol-üst köşe x (piksel, orijinal medya uzayı). */
  x: number;
  /** Sol-üst köşe y (piksel, orijinal medya uzayı). */
  y: number;
  width: number;
  height: number;
}

export interface Detection {
  /** Sonuç içinde benzersiz. İzleme (tracking) kimliği DEĞİLDİR. */
  id: string;
  /** Modelin sınıf kimliği; eşleme `ModelInfo.classes` içindedir ve AI tarafına aittir. */
  classId: number;
  className: string;
  /** 0–1 arası model skoru. Kalibre edilmiş olasılık olduğu varsayılmaz. */
  confidence: number;
  box: BoundingBox;
}

export interface FrameDetections {
  /** Kaynak videodaki kare indeksi (görüntüler için 0). */
  frameIndex: number;
  /** Kare zaman damgası, milisaniye. Görüntüler için 0. */
  timestampMs: number;
  detections: Detection[];
}

export type MediaKind = "image" | "video";

export interface MediaInfo {
  kind: MediaKind;
  /** Orijinal medya genişliği (piksel). Kutular bu uzaya göre ifade edilir. */
  width: number;
  height: number;
  /** Yalnızca video. */
  durationMs?: number;
  /** Kaynak video kare hızı; bilinmiyorsa belirtilmez. */
  fps?: number;
  /** Kaynak videodaki toplam kare sayısı; bilinmiyorsa belirtilmez. */
  totalFrames?: number;
}

export interface ModelClass {
  id: number;
  name: string;
}

export interface ModelInfo {
  /** Örn. "yolo11s". Mock için "mock-generator". */
  name: string;
  /** Ağırlık/kayıt sürümü; mock için null. */
  version: string | null;
  classes: ModelClass[];
}

export interface AnalysisTiming {
  processingMs: number;
  /** true: backend ölçümü. false: simülasyon süresi (mock). */
  measured: boolean;
}

export interface AnalysisResult {
  jobId: string;
  provenance: Provenance;
  model: ModelInfo;
  media: MediaInfo;
  /** Analiz edilen kareler (zaman sırasına göre artan). Görüntü: tek eleman. */
  frames: FrameDetections[];
  /** Backend'in uyguladığı minimum skor tabanı; altındaki tespitler döndürülmez. */
  minConfidenceApplied: number;
  /** Video: her N. kare analiz edildi (1 = tüm kareler). Görüntü: 1. */
  frameStride: number;
  timing: AnalysisTiming;
  createdAt: string; // ISO-8601 UTC
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export const TERMINAL_JOB_STATUSES: readonly JobStatus[] = ["succeeded", "failed", "canceled"];

export interface JobProgress {
  processedFrames: number;
  /** Toplam bilinmiyorsa null. */
  totalFrames: number | null;
  /** 0–1; bilinmiyorsa null (belirsiz ilerleme göstergesi kullanılır). */
  ratio: number | null;
}

export interface Job {
  id: string;
  kind: MediaKind;
  status: JobStatus;
  provenance: Provenance;
  progress: JobProgress;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  /** Yalnızca `failed`. */
  error: ApiError | null;
  /** `succeeded` olduğunda sonuç bu işaretçiyle alınır: GET /api/v1/jobs/{id}/result. */
  resultAvailable: boolean;
}

/** İstek parametreleri (multipart `options` alanı, JSON). */
export interface AnalysisOptions {
  /** 0–1. Backend bu değerin altındaki tespitleri döndürmez. Varsayılan 0.1. */
  minConfidence?: number;
  /** Yalnızca video: her N. kareyi analiz et (≥1). Varsayılan 1. */
  frameStride?: number;
}

export interface Capabilities {
  apiVersion: typeof API_VERSION;
  provenance: Provenance;
  model: ModelInfo | null;
  limits: UploadLimits;
}

export interface UploadLimits {
  maxImageBytes: number;
  maxVideoBytes: number;
  maxVideoDurationSeconds: number;
  imageMimeTypes: string[];
  videoMimeTypes: string[];
}

export type ServiceHealthStatus = "ok" | "degraded" | "unreachable";

export interface ServiceHealth {
  status: ServiceHealthStatus;
  /** Gerçek backend bağlı mı? Mock servis her zaman false. */
  backendConnected: boolean;
  provenance: Provenance;
  modelLoaded: boolean | null;
  checkedAt: string;
}

/* ------------------------------------------------------------------ */
/* Hatalar                                                             */
/* ------------------------------------------------------------------ */

/** Sunucunun döndürebileceği hata kodları. */
export type ServerErrorCode =
  | "invalid_request"
  | "unsupported_media_type"
  | "file_too_large"
  | "media_decode_failed"
  | "video_too_long"
  | "job_not_found"
  | "job_not_ready"
  | "model_unavailable"
  | "inference_failed"
  | "rate_limited"
  | "internal_error";

/** Yalnızca istemcide üretilen hata kodları (ağ, zaman aşımı, bozuk yanıt). */
export type ClientErrorCode = "network_error" | "timeout" | "invalid_response" | "aborted";

export type ApiErrorCode = ServerErrorCode | ClientErrorCode;

export interface ApiError {
  code: ApiErrorCode;
  /** Operatöre gösterilebilir, Türkçe veya İngilizce kısa mesaj. */
  message: string;
  /** Aynı isteği tekrar denemek mantıklı mı? */
  retryable: boolean;
  details?: Record<string, unknown>;
}

/** Tüm 4xx/5xx yanıt gövdesi. */
export interface ApiErrorEnvelope {
  error: ApiError;
}

/** Hata durumunu taşıyan, fırlatılabilir sınıf. */
export class ApiRequestError extends Error {
  readonly error: ApiError;
  readonly status: number | null;

  constructor(error: ApiError, status: number | null = null) {
    super(error.message);
    this.name = "ApiRequestError";
    this.error = error;
    this.status = status;
  }
}

/* ------------------------------------------------------------------ */
/* Servis arayüzü (mock ve HTTP istemcisi aynı arayüzü uygular)         */
/* ------------------------------------------------------------------ */

export interface CreateAnalysisInput {
  file: File;
  options?: AnalysisOptions;
}

export interface RequestOptions {
  signal?: AbortSignal;
}

export type DemoScenario = "success" | "failure";

export interface AnalysisService {
  readonly mode: "mock" | "http";
  getCapabilities(opts?: RequestOptions): Promise<Capabilities>;
  getHealth(opts?: RequestOptions): Promise<ServiceHealth>;
  /** Medya türüne göre görüntü ya da video işi oluşturur. */
  createAnalysis(input: CreateAnalysisInput, opts?: RequestOptions): Promise<Job>;
  getJob(jobId: string, opts?: RequestOptions): Promise<Job>;
  getResult(jobId: string, opts?: RequestOptions): Promise<AnalysisResult>;
  cancelJob(jobId: string, opts?: RequestOptions): Promise<Job>;
  /** Yalnızca mock serviste vardır: hata/başarı durumlarını sergilemek için. */
  demo?: {
    getScenario(): DemoScenario;
    setScenario(s: DemoScenario): void;
  };
}

/** Önerilen varsayılan limitler. Gerçek değerleri backend `capabilities` ile bildirir. */
export const DEFAULT_UPLOAD_LIMITS: UploadLimits = {
  maxImageBytes: 20 * 1024 * 1024,
  maxVideoBytes: 500 * 1024 * 1024,
  maxVideoDurationSeconds: 600,
  imageMimeTypes: ["image/jpeg", "image/png", "image/webp"],
  videoMimeTypes: ["video/mp4", "video/webm", "video/quicktime"],
};
