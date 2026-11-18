import { describe, expect, it } from "vitest";
import { DEFAULT_UPLOAD_LIMITS } from "@/lib/api/contract";
import { resolveMimeType, validateMediaFile } from "./validate";

const L = DEFAULT_UPLOAD_LIMITS;

describe("validateMediaFile", () => {
  it("MP4 videoyu kabul eder", () => {
    expect(validateMediaFile({ name: "a.mp4", type: "video/mp4", size: 1000 }, L)).toMatchObject({ ok: true, kind: "video" });
  });
  it("boş type için uzantıdan MIME çıkarır", () => {
    expect(resolveMimeType({ name: "x.MOV", type: "" })).toBe("video/quicktime");
  });
  it("desteklenmeyen türü reddeder", () => {
    const r = validateMediaFile({ name: "a.tiff", type: "image/tiff", size: 10 }, L);
    expect(r).toMatchObject({ ok: false, error: { code: "unsupported_media_type" } });
  });
  it("limit aşan görüntüyü reddeder", () => {
    const r = validateMediaFile({ name: "a.png", type: "image/png", size: L.maxImageBytes + 1 }, L);
    expect(r).toMatchObject({ ok: false, error: { code: "file_too_large" } });
  });
  it("sınırda olan dosyayı kabul eder", () => {
    expect(validateMediaFile({ name: "a.png", type: "image/png", size: L.maxImageBytes }, L).ok).toBe(true);
  });
  it("boş dosyayı reddeder", () => {
    expect(validateMediaFile({ name: "a.png", type: "image/png", size: 0 }, L).ok).toBe(false);
  });
});
