import type { ApiError, MediaKind, UploadLimits } from "@/lib/api/contract";
import { formatBytes } from "@/lib/format";

const EXTENSION_MIME: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  mp4: "video/mp4",
  m4v: "video/mp4",
  webm: "video/webm",
  mov: "video/quicktime",
};

/** Tarayıcı `file.type` boş bırakırsa uzantıdan MIME çıkarır. */
export function resolveMimeType(file: Pick<File, "name" | "type">): string {
  if (file.type) return file.type.toLowerCase();
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_MIME[ext] ?? "";
}

export type ValidationResult = { ok: true; kind: MediaKind; mimeType: string } | { ok: false; error: ApiError };

/** İstemci tarafı ön doğrulama. Sunucu aynı kuralları yeniden doğrulamak zorundadır. */
export function validateMediaFile(file: Pick<File, "name" | "type" | "size">, limits: UploadLimits): ValidationResult {
  const mimeType = resolveMimeType(file);
  const isImage = limits.imageMimeTypes.includes(mimeType);
  const isVideo = limits.videoMimeTypes.includes(mimeType);

  if (!isImage && !isVideo) {
    return {
      ok: false,
      error: {
        code: "unsupported_media_type",
        message: `Desteklenmeyen dosya türü${mimeType ? ` (${mimeType})` : ""}. Desteklenenler: JPEG, PNG, WebP, MP4, WebM, MOV.`,
        retryable: false,
      },
    };
  }
  if (file.size <= 0) {
    return { ok: false, error: { code: "invalid_request", message: "Dosya boş görünüyor.", retryable: false } };
  }
  const max = isImage ? limits.maxImageBytes : limits.maxVideoBytes;
  if (file.size > max) {
    return {
      ok: false,
      error: {
        code: "file_too_large",
        message: `Dosya çok büyük (${formatBytes(file.size)}). ${isImage ? "Görüntü" : "Video"} sınırı ${formatBytes(max)}.`,
        retryable: false,
      },
    };
  }
  return { ok: true, kind: isImage ? "image" : "video", mimeType };
}
