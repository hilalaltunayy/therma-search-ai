"use client";

import type { RefObject } from "react";
import { CircleSlash, LoaderCircle, TriangleAlert } from "lucide-react";
import { useAnalysis } from "@/state/analysis-store";
import { DEFAULT_UPLOAD_LIMITS } from "@/lib/api/contract";
import { formatTimestamp } from "@/lib/format";
import { Button, DemoBadge, ProgressBar, StateView } from "@/components/ui/primitives";
import { UploadDropzone } from "./upload-dropzone";
import { DetectionOverlay } from "./detection-overlay";
import { CompareHandle } from "./compare-handle";
import type { ViewPrefs } from "./view-prefs";
import type { RankedDetection } from "./ranked";

interface Props {
  videoRef: RefObject<HTMLVideoElement | null>;
  prefs: ViewPrefs;
  onPrefsChange: (p: ViewPrefs) => void;
  /** Eşik ve sınıf filtresi uygulanmış, geçerli kareye ait sıralı tespitler. */
  items: readonly RankedDetection[];
  /** Geçerli karede eşikten önceki tespit sayısı (HUD "görünür n / m"). */
  frameTotal: number;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  timeMs: number;
}

/**
 * Görüntüleme sahnesi. Izgara: üst HUD satırı · kare · alt cetvel/DEMO satırı.
 * HUD çipleri karenin dışındadır; tespit kutularını hiçbir zaman örtmez.
 * HUD'daki her değer gerçek veriden gelir (medya boyutu, oynatma zamanı, sonuç sayıları, eşik).
 */
export function MediaStage({ videoRef, prefs, onPrefsChange, items, frameTotal, selectedId, hoveredId, onSelect, onHover, timeMs }: Props) {
  const { state, capabilities, selectFile, dismissSelectionError, start, cancel, threshold } = useAnalysis();
  const { phase, probe, mediaUrl, file, kind, result, job, error, selectionError } = state;

  if (phase === "empty" || !probe || !mediaUrl || !file) {
    return (
      <div className="stage h-full min-h-[420px] overflow-hidden rounded-2xl border border-line" style={{ gridTemplateRows: "minmax(0,1fr)" }}>
        <UploadDropzone
          limits={capabilities?.limits ?? DEFAULT_UPLOAD_LIMITS}
          error={selectionError}
          onDismissError={dismissSelectionError}
          onFile={selectFile}
        />
      </div>
    );
  }

  const ratio = probe.width / probe.height;
  const succeeded = phase === "succeeded" && result !== null;
  const split = succeeded && prefs.mode === "split";
  const showOverlay = succeeded && prefs.mode !== "original" && prefs.showBoxes;
  const isMock = result?.provenance === "mock";

  return (
    <div
      className="stage h-full overflow-hidden rounded-2xl border border-line"
      style={{ ["--ratio" as string]: String(ratio) }}
      aria-label="Görüntüleme alanı"
    >
      {/* Üst HUD satırı */}
      <div className="flex min-w-0 items-center justify-between gap-2 px-3 lg:pl-[44px] lg:pr-4">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="hud-chip">
            <em>KAYNAK</em> {probe.width}×{probe.height} px
          </span>
          {kind === "video" && (
            <span className="hud-chip">
              <em>t</em> <span className="text-orange-text">{formatTimestamp(timeMs)}</span>
            </span>
          )}
        </div>
        {succeeded && (
          <div className="flex items-center gap-1.5">
            <span className="hud-chip" title="Geçerli karede eşik üstü / toplam tespit">
              <em className="hidden sm:inline">KAREDE</em> {items.length} / {frameTotal}
            </span>
            <span className="hud-chip hidden sm:inline-flex">
              <em>EŞİK</em> ≥ {threshold.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* Kare */}
      <div className="stage-frame-cell">
        <div className="stage-frame">
          <span className="bracket tl" />
          <span className="bracket tr" />
          <span className="bracket bl" />
          <span className="bracket br" />

          {/* Cetvel: gerçek medya piksel boyutu (koordinat okumasına yardımcı) */}
          <div aria-hidden className="pointer-events-none absolute -left-[40px] inset-y-0 hidden w-8 flex-col justify-between text-right font-mono text-[11px] leading-none text-subtle lg:flex">
            <span>0</span>
            <span>{Math.round(probe.height / 2)}</span>
            <span>{probe.height}</span>
          </div>
          <div aria-hidden className="pointer-events-none absolute inset-x-0 top-[calc(100%+6px)] hidden justify-between font-mono text-[11px] leading-none text-subtle lg:flex">
            <span>0</span>
            <span>{Math.round(probe.width / 2)}</span>
            <span>{probe.width}</span>
          </div>

          <div className="absolute inset-0 overflow-hidden rounded-[3px] bg-black">
            {kind === "video" ? (
              <video ref={videoRef} src={mediaUrl} muted playsInline preload="auto" className="absolute inset-0 size-full" aria-label={`Yüklenen video: ${file.name}`} />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element -- blob URL; next/image uygun değil
              <img src={mediaUrl} alt={`Yüklenen termal görüntü: ${file.name}`} className="absolute inset-0 size-full" draggable={false} />
            )}
          </div>

          {showOverlay && result && (
            <div className="absolute inset-0" style={split ? { clipPath: `inset(-40px -40px -40px ${prefs.splitPct}%)` } : undefined}>
              <DetectionOverlay
                items={items}
                media={result.media}
                showLabels={prefs.showLabels}
                selectedId={selectedId}
                hoveredId={hoveredId}
                onSelect={onSelect}
                onHover={onHover}
                interactive={!split}
              />
            </div>
          )}

          {split && (
            <>
              <CompareHandle value={prefs.splitPct} onChange={(splitPct) => onPrefsChange({ ...prefs, splitPct })} />
              <span className="hud-chip pointer-events-none absolute bottom-2 left-2 z-30">ORİJİNAL</span>
              <span className="hud-chip pointer-events-none absolute bottom-2 right-2 z-30 text-cyan">TESPİTLİ</span>
            </>
          )}

          {(phase === "submitting" || phase === "processing") && (
            <div role="status" aria-live="polite" className="absolute inset-0 z-40 grid place-items-center overflow-hidden bg-base/45">
              <div aria-hidden className="animate-scan absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-transparent via-cyan/15 to-transparent" />
              <div className="glass glass-edge w-80 max-w-[88%] rounded-2xl p-5">
                <p className="flex items-center gap-2 text-[15px] font-semibold text-ink">
                  <LoaderCircle className="size-5 animate-spin text-cyan" aria-hidden />
                  {phase === "submitting" ? "İş oluşturuluyor…" : job?.status === "queued" ? "Kuyrukta…" : "Analiz ediliyor…"}
                </p>
                <div className="mt-4">
                  <ProgressBar label="Analiz ilerlemesi" ratio={phase === "submitting" ? null : (job?.progress.ratio ?? null)} />
                </div>
                <p className="tnum mt-2 flex justify-between font-mono text-[13px] text-muted">
                  <span>{job?.progress.totalFrames != null ? `${job.progress.processedFrames} / ${job.progress.totalFrames} kare` : "—"}</span>
                  <span>{job?.progress.ratio != null ? `%${Math.round(job.progress.ratio * 100)}` : ""}</span>
                </p>
                {job?.provenance === "mock" && <p className="mt-2 text-[13px] text-amber">DEMO: simüle edilmiş ilerleme; gerçek çıkarım değil.</p>}
                <Button variant="secondary" size="sm" className="mt-4 w-full" onClick={() => void cancel()}>
                  İptal et
                </Button>
              </div>
            </div>
          )}

          {phase === "failed" && (
            <div className="absolute inset-0 z-40 grid place-items-center bg-base/70 backdrop-blur-[2px]">
              <div className="glass rounded-2xl">
                <StateView
                  role="alert"
                  tone="danger"
                  icon={<TriangleAlert className="size-6" aria-hidden />}
                  title="Analiz tamamlanamadı"
                  description={
                    <>
                      {error?.message ?? "Bilinmeyen hata."}
                      {error && <span className="mt-1 block font-mono text-[13px] text-subtle">kod: {error.code}</span>}
                    </>
                  }
                  action={error?.retryable === false ? undefined : <Button variant="primary" onClick={() => void start()}>Yeniden dene</Button>}
                />
              </div>
            </div>
          )}

          {phase === "canceled" && (
            <div className="absolute inset-0 z-40 grid place-items-center bg-base/70 backdrop-blur-[2px]">
              <div className="glass rounded-2xl">
                <StateView
                  role="status"
                  tone="amber"
                  icon={<CircleSlash className="size-6" aria-hidden />}
                  title="Analiz iptal edildi"
                  description="Dosya hâlâ yüklü. Analizi yeniden başlatabilirsiniz."
                  action={<Button variant="primary" onClick={() => void start()}>Yeniden başlat</Button>}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Alt satır: DEMO etiketi / önizleme durumu (karenin dışında) */}
      <div className="flex items-end justify-between gap-2 px-3 pb-2 lg:pl-[44px] lg:pr-4">
        {succeeded ? (
          isMock ? (
            <DemoBadge label="DEMO / MOCK — kutular yapay" />
          ) : (
            <span className="hud-chip"><em>MODEL</em> {result.model.name}</span>
          )
        ) : phase === "ready" ? (
          <span className="hud-chip"><em>DURUM</em> önizleme · analiz başlatılmadı</span>
        ) : (
          <span />
        )}
      </div>
    </div>
  );
}
