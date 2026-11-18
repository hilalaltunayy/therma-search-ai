import {
  ApiRequestError,
  DEFAULT_UPLOAD_LIMITS,
  type AnalysisResult,
  type AnalysisService,
  type ApiError,
  type Capabilities,
  type CreateAnalysisInput,
  type DemoScenario,
  type Detection,
  type FrameDetections,
  type Job,
  type MediaInfo,
  type ModelInfo,
  type ServiceHealth,
} from "./contract";
import { probeMedia, type MediaProbe } from "@/lib/media/probe";
import { resolveMimeType } from "@/lib/media/validate";

/**
 * DEMO / MOCK servis — GERÇEK MODEL YOKTUR.
 *
 * Üretilen tüm kutular ve skorlar yapay, tohumlu (seeded) rastgele sayılardır; yüklenen medyanın
 * içeriğiyle ilgisi yoktur. Sonuçlar `provenance: "mock"` taşır ve arayüz bunu her zaman belirtir.
 * Süreler simülasyondur (`timing.measured = false`).
 */

export const MOCK_MODEL: ModelInfo = {
  name: "mock-generator",
  version: null,
  classes: [{ id: 0, name: "person" }],
};

export interface MockServiceOptions {
  /** Test için enjekte edilebilir; varsayılan tarayıcı probe'u. */
  probe?: (file: File, kind: "image" | "video") => Promise<MediaProbe>;
  /** Simüle edilen işlem süreleri (ms). */
  imageJobMs?: number;
  videoJobMs?: number;
  now?: () => number;
}

/** Küçük, deterministik PRNG (mulberry32). */
export function createRng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashSeed(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const MOCK_SAMPLE_FPS = 5;

interface Track {
  x: number;
  y: number;
  vx: number;
  vy: number;
  w: number;
  h: number;
  baseConf: number;
  startMs: number;
  endMs: number;
}

function clampBox(x: number, y: number, w: number, h: number, media: MediaInfo) {
  const cx = Math.min(Math.max(0, x), media.width - w);
  const cy = Math.min(Math.max(0, y), media.height - h);
  return { x: Math.round(cx * 10) / 10, y: Math.round(cy * 10) / 10, width: Math.round(w * 10) / 10, height: Math.round(h * 10) / 10 };
}

/** Saf fonksiyon: aynı tohum + medya → aynı yapay sonuç (test edilebilir). */
export function generateMockFrames(seed: number, media: MediaInfo): { frames: FrameDetections[]; frameStride: number } {
  const rng = createRng(seed);
  const trackCount = 3 + Math.floor(rng() * 5);
  const durationMs = media.kind === "video" ? Math.max(media.durationMs ?? 1000, 1) : 0;

  const tracks: Track[] = Array.from({ length: trackCount }, () => {
    const w = media.width * (0.035 + rng() * 0.03);
    const h = w * (1.5 + rng() * 0.4);
    const start = media.kind === "video" ? Math.floor(rng() * durationMs * 0.5) : 0;
    const end = media.kind === "video" ? Math.min(durationMs, start + durationMs * (0.35 + rng() * 0.65)) : 0;
    return {
      x: rng() * (media.width - w),
      y: rng() * (media.height - h),
      vx: (rng() - 0.5) * media.width * 0.02,
      vy: (rng() - 0.5) * media.height * 0.02,
      w,
      h,
      // Bazı izler bilerek düşük skorludur; eşik kaydırıcısı anlamlı çalışsın.
      baseConf: rng() < 0.3 ? 0.12 + rng() * 0.3 : 0.55 + rng() * 0.42,
      startMs: start,
      endMs: end,
    };
  });

  const timestamps: number[] = [];
  if (media.kind === "image") timestamps.push(0);
  else for (let t = 0; t <= durationMs; t += 1000 / MOCK_SAMPLE_FPS) timestamps.push(Math.round(t));

  const fps = media.fps ?? 30;
  const frames: FrameDetections[] = timestamps.map((ts, fi) => {
    const detections: Detection[] = [];
    tracks.forEach((tr, ti) => {
      if (media.kind === "video" && (ts < tr.startMs || ts > tr.endMs)) return;
      const sec = ts / 1000;
      const jitter = (rng() - 0.5) * 0.08;
      const conf = Math.min(0.99, Math.max(0.05, tr.baseConf + jitter));
      const box = clampBox(tr.x + tr.vx * sec, tr.y + tr.vy * sec, tr.w, tr.h, media);
      detections.push({ id: `mock-${fi}-${ti}`, classId: 0, className: "person", confidence: Math.round(conf * 1000) / 1000, box });
    });
    return { frameIndex: Math.round((ts / 1000) * fps), timestampMs: ts, detections };
  });
  return { frames, frameStride: 1 };
}

interface MockJobRecord {
  job: Omit<Job, "status" | "progress" | "resultAvailable" | "startedAt" | "finishedAt" | "error">;
  media: MediaInfo;
  seed: number;
  startedAtMs: number;
  durationMs: number;
  scenario: DemoScenario;
  canceled: boolean;
  totalFrames: number;
}

export function createMockAnalysisService(options: MockServiceOptions = {}): AnalysisService {
  const now = options.now ?? (() => Date.now());
  const probe = options.probe ?? probeMedia;
  const imageJobMs = options.imageJobMs ?? 1800;
  const videoJobMs = options.videoJobMs ?? 4200;
  const jobs = new Map<string, MockJobRecord>();
  let scenario: DemoScenario = "success";
  let counter = 0;

  const iso = (ms: number) => new Date(ms).toISOString();

  function notFound(id: string): ApiRequestError {
    const error: ApiError = { code: "job_not_found", message: `İş bulunamadı: ${id}`, retryable: false };
    return new ApiRequestError(error, 404);
  }

  function snapshot(rec: MockJobRecord): Job {
    const elapsed = now() - rec.startedAtMs;
    const queuedMs = 350;
    let status: Job["status"];
    let ratio: number;
    if (rec.canceled) {
      status = "canceled";
      ratio = Math.min(1, Math.max(0, (elapsed - queuedMs) / rec.durationMs));
    } else if (elapsed < queuedMs) {
      status = "queued";
      ratio = 0;
    } else if (elapsed - queuedMs < rec.durationMs) {
      status = "running";
      ratio = (elapsed - queuedMs) / rec.durationMs;
    } else {
      status = rec.scenario === "failure" ? "failed" : "succeeded";
      ratio = rec.scenario === "failure" ? 0.62 : 1;
    }
    const failed = status === "failed";
    return {
      ...rec.job,
      status,
      progress: { processedFrames: Math.round(rec.totalFrames * ratio), totalFrames: rec.totalFrames, ratio },
      startedAt: status === "queued" ? null : iso(rec.startedAtMs + queuedMs),
      finishedAt: ["succeeded", "failed", "canceled"].includes(status) ? iso(rec.startedAtMs + queuedMs + rec.durationMs) : null,
      error: failed
        ? { code: "inference_failed", message: "DEMO hata senaryosu: simüle edilmiş çıkarım hatası (gerçek bir hata değildir).", retryable: true }
        : null,
      resultAvailable: status === "succeeded",
    };
  }

  return {
    mode: "mock",

    async getCapabilities(): Promise<Capabilities> {
      return { apiVersion: "v1", provenance: "mock", model: MOCK_MODEL, limits: DEFAULT_UPLOAD_LIMITS };
    },

    async getHealth(): Promise<ServiceHealth> {
      return { status: "ok", backendConnected: false, provenance: "mock", modelLoaded: false, checkedAt: iso(now()) };
    },

    async createAnalysis({ file }: CreateAnalysisInput): Promise<Job> {
      const kind = resolveMimeType(file).startsWith("video/") ? "video" : "image";
      let probed: MediaProbe;
      try {
        probed = await probe(file, kind);
      } catch (e) {
        throw new ApiRequestError(
          { code: "media_decode_failed", message: e instanceof Error ? e.message : "Medya çözülemedi.", retryable: false },
          422,
        );
      }
      counter += 1;
      const id = `mock-job-${counter}`;
      const media: MediaInfo = { kind, width: probed.width, height: probed.height, durationMs: probed.durationMs };
      const totalFrames = kind === "image" ? 1 : Math.max(1, Math.round(((probed.durationMs ?? 1000) / 1000) * MOCK_SAMPLE_FPS));
      jobs.set(id, {
        job: { id, kind, provenance: "mock", createdAt: iso(now()) },
        media,
        seed: hashSeed(`${file.name}|${file.size}|${file.lastModified}`),
        startedAtMs: now(),
        durationMs: kind === "image" ? imageJobMs : videoJobMs,
        scenario,
        canceled: false,
        totalFrames,
      });
      return snapshot(jobs.get(id)!);
    },

    async getJob(id) {
      const rec = jobs.get(id);
      if (!rec) throw notFound(id);
      return snapshot(rec);
    },

    async getResult(id): Promise<AnalysisResult> {
      const rec = jobs.get(id);
      if (!rec) throw notFound(id);
      if (snapshot(rec).status !== "succeeded") {
        throw new ApiRequestError({ code: "job_not_ready", message: "Sonuç henüz hazır değil.", retryable: true }, 409);
      }
      const { frames, frameStride } = generateMockFrames(rec.seed, rec.media);
      return {
        jobId: id,
        provenance: "mock",
        model: MOCK_MODEL,
        media: rec.media,
        frames,
        minConfidenceApplied: 0.05,
        frameStride,
        timing: { processingMs: rec.durationMs, measured: false },
        createdAt: rec.job.createdAt,
      };
    },

    async cancelJob(id) {
      const rec = jobs.get(id);
      if (!rec) throw notFound(id);
      if (!["succeeded", "failed"].includes(snapshot(rec).status)) rec.canceled = true;
      return snapshot(rec);
    },

    demo: {
      getScenario: () => scenario,
      setScenario: (s) => {
        scenario = s;
      },
    },
  };
}
