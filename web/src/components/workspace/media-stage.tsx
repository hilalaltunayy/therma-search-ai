"use client";

import type { RefObject } from "react";
import { CircleSlash, LoaderCircle, TriangleAlert } from "lucide-react";
import { useAnalysis } from "@/state/analysis-store";
import type { Detection } from "@/lib/api/contract";
import { DemoBadge, Button, ProgressBar, StateView } from "@/components/ui/primitives";
import { UploadDropzone } from "./upload-dropzone";
import { DetectionOverlay } from "./detection-overlay";
import { CompareHandle } from "./compare-handle";
import type { ViewPrefs } from "./view-prefs";
import { DEFAULT_UPLOAD_LIMITS } from "@/lib/api/contract";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  prefs: ViewPrefs;
  onPrefsChange: (p: ViewPrefs) => void;
  /** Eşik ve sınıf filtresi uygulanmış, geçerli kareye ait tespitler. */
  visibleDetections: readonly Detection[];
  selectedId: string | null;
}

export function MediaStage({ videoRef, prefs, onPrefsChange, visibleDetections, selectedId }: Props) {
  const { state, capabilities, selectFile, dismissSelectionError, start, cancel } = useAnalysis();
  const { phase, probe, mediaUrl, file, kind, result, job, error, selectionError } = state;

  if (phase === "empty" || !probe || !mediaUrl || !file) {
    return (
      <UploadDropzone
        limits={capabilities?.limits ?? DEFAULT_UPLOAD_LIMITS}
        error={selectionError}
        onDismissError={dismissSelectionError}
        onFile={selectFile}
      />
    );
  }

  const ratio = probe.width / probe.height;
  const showOverlay = phase === "succeeded" && result !== null && prefs.mode !== "original" && prefs.showBoxes;
  const split = phase === "succeeded" && prefs.mode === "split";
  const isMock = result?.provenance === "mock";

  return (
    <div className="flex min-h-[420px] items-center justify-center bg-black/40 p-2 sm:p-4">
      <div
        className="relative overflow-hidden rounded-lg border border-line bg-black"
        style={{ aspectRatio: `${ratio}`, width: `min(100%, calc(68vh * ${ratio}))` }}
      >
        {kind === "video" ? (
          <video ref={videoRef} src={mediaUrl} muted playsInline preload="auto" className="absolute inset-0 size-full" aria-label={`Yüklenen video: ${file.name}`} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- blob URL; next/image uygun değil
          <img src={mediaUrl} alt={`Yüklenen termal görüntü: ${file.name}`} className="absolute inset-0 size-full" draggable={false} />
        )}

        {showOverlay && result && (
          <div className="absolute inset-0" style={split ? { clipPath: `inset(0 0 0 ${prefs.splitPct}%)` } : undefined}>
            <DetectionOverlay detections={visibleDetections} media={result.media} showLabels={prefs.showLabels} selectedId={selectedId} />
          </div>
        )}

        {split && <CompareHandle value={prefs.splitPct} onChange={(splitPct) => onPrefsChange({ ...prefs, splitPct })} />}

        {phase === "succeeded" && (
          <div className="pointer-events-none absolute left-2 top-2 flex flex-wrap gap-1.5">
            {split && <span className="rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-white">ORİJİNAL</span>}
            {split && <span className="rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-accent">İŞLENMİŞ</span>}
            {isMock && <DemoBadge />}
          </div>
        )}

        {/* --- Durum katmanları --- */}
        {phase === "ready" && (
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3 text-xs text-muted">
            Önizleme · analiz henüz başlatılmadı. Sağ paneldeki <strong className="text-ink">Analizi başlat</strong> düğmesini kullanın.
          </div>
        )}

        {(phase === "submitting" || phase === "processing") && (
          <div role="status" aria-live="polite" className="absolute inset-0 grid place-items-center bg-base/55 backdrop-blur-[1px]">
            <div aria-hidden className="absolute inset-x-0 h-1/3 animate-scan bg-gradient-to-b from-transparent via-accent/15 to-transparent" />
            <div className="w-72 max-w-[85%] rounded-xl border border-line-strong bg-surface/95 p-4 shadow-xl">
              <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                <LoaderCircle className="size-4 animate-spin text-accent" aria-hidden />
                {phase === "submitting" ? "İş oluşturuluyor…" : job?.status === "queued" ? "Kuyrukta…" : "İşleniyor…"}
              </div>
              <div className="mt-3">
                <ProgressBar label="Analiz ilerlemesi" ratio={phase === "submitting" ? null : (job?.progress.ratio ?? null)} />
              </div>
              <div className="tnum mt-2 flex justify-between text-[11px] text-subtle">
                <span>
                  {job?.progress.totalFrames != null ? `${job.progress.processedFrames}/${job.progress.totalFrames} kare` : "—"}
                </span>
                <span>{job?.progress.ratio != null ? `%${Math.round(job.progress.ratio * 100)}` : ""}</span>
              </div>
              {job?.provenance === "mock" && <p className="mt-2 text-[11px] text-warn">DEMO: simüle edilmiş ilerleme, gerçek çıkarım değil.</p>}
              <Button variant="ghost" size="sm" className="mt-3 w-full" onClick={() => void cancel()}>
                İptal et
              </Button>
            </div>
          </div>
        )}

        {phase === "failed" && (
          <div className="absolute inset-0 grid place-items-center bg-base/75 backdrop-blur-[2px]">
            <StateView
              role="alert"
              tone="danger"
              icon={<TriangleAlert className="size-5" aria-hidden />}
              title="Analiz tamamlanamadı"
              description={
                <>
                  {error?.message ?? "Bilinmeyen hata."}
                  {error && <span className="mt-1 block font-mono text-[11px] text-subtle">kod: {error.code}</span>}
                </>
              }
              action={error?.retryable === false ? undefined : <Button variant="primary" onClick={() => void start()}>Yeniden dene</Button>}
            />
          </div>
        )}

        {phase === "canceled" && (
          <div className="absolute inset-0 grid place-items-center bg-base/75 backdrop-blur-[2px]">
            <StateView
              role="status"
              icon={<CircleSlash className="size-5" aria-hidden />}
              title="Analiz iptal edildi"
              description="Dosya hâlâ yüklü. İsterseniz analizi yeniden başlatabilirsiniz."
              action={<Button variant="primary" onClick={() => void start()}>Yeniden başlat</Button>}
            />
          </div>
        )}
      </div>
    </div>
  );
}
