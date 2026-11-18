import { describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "./contract";
import { assertAnalysisResult } from "./guards";
import { createHttpAnalysisService } from "./http-client";
import { createMockAnalysisService, generateMockFrames, hashSeed } from "./mock-service";
import { resolveApiMode } from "./index";

const probe = async (_f: File, kind: "image" | "video") =>
  kind === "image" ? { kind, width: 640, height: 512 } : { kind, width: 640, height: 512, durationMs: 3000 };

describe("mock servis", () => {
  const imageFile = new File([new Uint8Array(10)], "scene.png", { type: "image/png" });

  it("aynı tohum aynı sonucu üretir ve kutular sınırların içindedir", () => {
    const media = { kind: "video" as const, width: 640, height: 512, durationMs: 4000 };
    const a = generateMockFrames(hashSeed("x"), media);
    const b = generateMockFrames(hashSeed("x"), media);
    expect(a).toEqual(b);
    for (const f of a.frames) for (const d of f.detections) {
      expect(d.box.x).toBeGreaterThanOrEqual(0);
      expect(d.box.x + d.box.width).toBeLessThanOrEqual(640.01);
      expect(d.box.y + d.box.height).toBeLessThanOrEqual(512.01);
      expect(d.confidence).toBeGreaterThanOrEqual(0);
      expect(d.confidence).toBeLessThanOrEqual(1);
    }
  });

  it("sonuç MOCK olarak işaretlenir ve simüle süre ölçülmüş sayılmaz", async () => {
    let t = 0;
    const svc = createMockAnalysisService({ probe, now: () => t, imageJobMs: 1000 });
    const job = await svc.createAnalysis({ file: imageFile });
    expect(job.provenance).toBe("mock");
    expect(job.status).toBe("queued");
    t = 200;
    expect((await svc.getJob(job.id)).status).toBe("queued");
    t = 800;
    const running = await svc.getJob(job.id);
    expect(running.status).toBe("running");
    expect(running.progress.ratio).toBeGreaterThan(0);
    await expect(svc.getResult(job.id)).rejects.toMatchObject({ error: { code: "job_not_ready" } });
    t = 5000;
    expect((await svc.getJob(job.id)).status).toBe("succeeded");
    const result = await svc.getResult(job.id);
    expect(result.provenance).toBe("mock");
    expect(result.timing.measured).toBe(false);
    expect(result.model.version).toBeNull();
    expect(() => assertAnalysisResult(result)).not.toThrow();
  });

  it("hata senaryosu failed durumu ve tekrar denenebilir hata üretir", async () => {
    let t = 0;
    const svc = createMockAnalysisService({ probe, now: () => t, imageJobMs: 100 });
    svc.demo!.setScenario("failure");
    const job = await svc.createAnalysis({ file: imageFile });
    t = 10_000;
    const done = await svc.getJob(job.id);
    expect(done.status).toBe("failed");
    expect(done.error).toMatchObject({ code: "inference_failed", retryable: true });
    expect(done.resultAvailable).toBe(false);
  });

  it("iptal edilen iş canceled olur; bilinmeyen iş 404 benzeri hata verir", async () => {
    const t = 0;
    const svc = createMockAnalysisService({ probe, now: () => t });
    const job = await svc.createAnalysis({ file: imageFile });
    expect((await svc.cancelJob(job.id)).status).toBe("canceled");
    await expect(svc.getJob("yok")).rejects.toMatchObject({ error: { code: "job_not_found" } });
  });

  it("çözülemeyen medya media_decode_failed verir", async () => {
    const svc = createMockAnalysisService({ probe: async () => { throw new Error("bozuk"); } });
    await expect(svc.createAnalysis({ file: imageFile })).rejects.toMatchObject({ error: { code: "media_decode_failed" } });
  });
});

describe("assertAnalysisResult", () => {
  const base = (box: Record<string, number>, confidence = 0.9): unknown => ({
    jobId: "j", provenance: "model", model: { name: "m", version: "1", classes: [] }, media: { kind: "image", width: 100, height: 100 },
    frames: [{ frameIndex: 0, timestampMs: 0, detections: [{ id: "a", classId: 0, className: "person", confidence, box }] }],
    minConfidenceApplied: 0.1, frameStride: 1, timing: { processingMs: 1, measured: true }, createdAt: "x",
  } satisfies Record<string, unknown>);

  it("geçerli sonucu kabul eder", () => {
    expect(() => assertAnalysisResult(base({ x: 1, y: 1, width: 10, height: 10 }))).not.toThrow();
  });
  it("sınır dışı kutuyu reddeder", () => {
    expect(() => assertAnalysisResult(base({ x: 95, y: 1, width: 10, height: 10 }))).toThrow(ApiRequestError);
  });
  it("normalize (0–1) kutuyu yanlışlıkla piksel sanmaz: genişlik<=0 veya sınır ihlali yakalanır", () => {
    expect(() => assertAnalysisResult(base({ x: 0.1, y: 0.1, width: 0, height: 0.2 }))).toThrow();
  });
  it("0–1 dışındaki skoru reddeder", () => {
    expect(() => assertAnalysisResult(base({ x: 1, y: 1, width: 10, height: 10 }, 1.2))).toThrow();
  });
});

describe("http istemcisi (sahte fetch ile)", () => {
  const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

  it("video dosyasını /analyses/video adresine multipart olarak yollar", async () => {
    const fetchImpl = vi.fn(async () => json(202, { id: "j1", kind: "video", status: "queued", provenance: "model", progress: { processedFrames: 0, totalFrames: null, ratio: null }, createdAt: "", startedAt: null, finishedAt: null, error: null, resultAvailable: false }));
    const svc = createHttpAnalysisService({ baseUrl: "http://x/", fetchImpl: fetchImpl as unknown as typeof fetch });
    const job = await svc.createAnalysis({ file: new File([new Uint8Array(3)], "a.mp4", { type: "video/mp4" }), options: { minConfidence: 0.1 } });
    expect(job.id).toBe("j1");
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://x/api/v1/analyses/video");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("hata zarfını ApiRequestError'a çevirir", async () => {
    const env = { error: { code: "file_too_large", message: "büyük", retryable: false } };
    const svc = createHttpAnalysisService({ baseUrl: "http://x", fetchImpl: (async () => json(413, env)) as unknown as typeof fetch });
    await expect(svc.getJob("j")).rejects.toMatchObject({ status: 413, error: { code: "file_too_large" } });
  });

  it("ağ hatasını network_error olarak bildirir; sağlık 'unreachable' döner", async () => {
    const svc = createHttpAnalysisService({ baseUrl: "http://x", fetchImpl: (async () => { throw new TypeError("fail"); }) as unknown as typeof fetch });
    await expect(svc.getJob("j")).rejects.toMatchObject({ error: { code: "network_error", retryable: true } });
    expect(await svc.getHealth()).toMatchObject({ status: "unreachable", backendConnected: false });
  });

  it("JSON olmayan 502 yanıtını retryable sunucu hatası yapar", async () => {
    const svc = createHttpAnalysisService({ baseUrl: "http://x", fetchImpl: (async () => new Response("bad gateway", { status: 502 })) as unknown as typeof fetch });
    await expect(svc.getJob("j")).rejects.toMatchObject({ error: { retryable: true } });
  });
});

describe("servis seçimi", () => {
  it("varsayılan mock; yalnızca 'http' gerçek istemciyi seçer", () => {
    expect(resolveApiMode(undefined)).toBe("mock");
    expect(resolveApiMode("whatever")).toBe("mock");
    expect(resolveApiMode("http")).toBe("http");
  });
});

