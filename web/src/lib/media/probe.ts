import type { MediaKind } from "@/lib/api/contract";

export interface MediaProbe {
  kind: MediaKind;
  width: number;
  height: number;
  /** Yalnızca video. */
  durationMs?: number;
}

/**
 * Tarayıcının dosyayı çözebildiğini ve gerçek piksel boyutunu doğrular (yalnızca tarayıcıda çalışır).
 * Kutu koordinatları bu boyutlara göre yorumlanır; bu yüzden tahmin değil ölçüm kullanılır.
 */
export function probeMedia(file: File, kind: MediaKind): Promise<MediaProbe> {
  const url = URL.createObjectURL(file);
  return new Promise<MediaProbe>((resolve, reject) => {
    const done = () => URL.revokeObjectURL(url);
    if (kind === "image") {
      const img = new Image();
      img.onload = () => {
        done();
        resolve({ kind, width: img.naturalWidth, height: img.naturalHeight });
      };
      img.onerror = () => {
        done();
        reject(new Error("Tarayıcı bu görüntüyü çözemedi."));
      };
      img.src = url;
    } else {
      const video = document.createElement("video");
      video.preload = "metadata";
      video.muted = true;
      video.onloadedmetadata = () => {
        const probe: MediaProbe = {
          kind,
          width: video.videoWidth,
          height: video.videoHeight,
          durationMs: Number.isFinite(video.duration) ? Math.round(video.duration * 1000) : undefined,
        };
        done();
        resolve(probe);
      };
      video.onerror = () => {
        done();
        reject(new Error("Tarayıcı bu videoyu oynatamıyor (codec desteklenmiyor olabilir)."));
      };
      video.src = url;
    }
  });
}
