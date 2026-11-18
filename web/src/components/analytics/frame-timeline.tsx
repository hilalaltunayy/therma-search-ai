"use client";

import { useMemo, type KeyboardEvent, type MouseEvent } from "react";
import type { FrameDetections } from "@/lib/api/contract";
import { bucketFrames } from "@/lib/detections/utils";
import { formatTimestamp } from "@/lib/format";

interface Props {
  frames: readonly FrameDetections[];
  durationMs: number;
  threshold: number;
  /** Oynatma konumu; verilmezse imleç çizilmez. */
  playheadMs?: number;
  onSeek?: (ms: number) => void;
}

/** Kare zaman çizelgesi: her çubuk, o zaman diliminde eşik üstü en yüksek kare başına tespit sayısıdır. */
export function FrameTimeline({ frames, durationMs, threshold, playheadMs, onSeek }: Props) {
  const buckets = useMemo(() => bucketFrames(frames, durationMs, threshold, 120), [frames, durationMs, threshold]);
  const peak = Math.max(1, ...buckets.map((b) => b.peak));
  const interactive = Boolean(onSeek);

  const seekFromX = (e: MouseEvent<HTMLDivElement>) => {
    if (!onSeek) return;
    const rect = e.currentTarget.getBoundingClientRect();
    onSeek(Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) * durationMs);
  };
  const onKey = (e: KeyboardEvent) => {
    if (!onSeek || playheadMs === undefined) return;
    const step = Math.max(durationMs / 100, 200);
    if (e.key === "ArrowLeft") onSeek(Math.max(0, playheadMs - step));
    else if (e.key === "ArrowRight") onSeek(Math.min(durationMs, playheadMs + step));
    else return;
    e.preventDefault();
  };

  return (
    <div>
      <div
        className={`relative flex h-20 items-end gap-px rounded-md border border-line bg-base px-1 ${interactive ? "cursor-pointer" : ""}`}
        onClick={seekFromX}
        role={interactive ? "slider" : "img"}
        tabIndex={interactive ? 0 : undefined}
        onKeyDown={onKey}
        aria-label={interactive ? "Tespit zaman çizelgesi; konuma gitmek için tıklayın" : "Tespit zaman çizelgesi"}
        aria-valuemin={interactive ? 0 : undefined}
        aria-valuemax={interactive ? Math.round(durationMs) : undefined}
        aria-valuenow={interactive ? Math.round(playheadMs ?? 0) : undefined}
        aria-valuetext={interactive ? formatTimestamp(playheadMs ?? 0) : undefined}
      >
        {buckets.map((b, i) => (
          <div key={i} className="flex h-full flex-1 items-end" title={b.analyzed ? `${formatTimestamp(b.startMs)} · en çok ${b.peak} tespit` : `${formatTimestamp(b.startMs)} · analiz edilmedi`}>
            {b.analyzed ? (
              <div
                className={b.peak > 0 ? "w-full rounded-t-[1px] bg-accent/80" : "h-px w-full bg-line-strong"}
                style={b.peak > 0 ? { height: `${Math.max(8, (b.peak / peak) * 100)}%` } : undefined}
              />
            ) : (
              <div className="h-px w-full bg-line" />
            )}
          </div>
        ))}
        {playheadMs !== undefined && durationMs > 0 && (
          <div aria-hidden className="pointer-events-none absolute inset-y-0 w-0.5 bg-white" style={{ left: `${(playheadMs / durationMs) * 100}%` }} />
        )}
      </div>
      <div className="tnum mt-1.5 flex justify-between text-[10px] text-subtle">
        <span>{formatTimestamp(0)}</span>
        <span>Çubuk yüksekliği: kare başına en çok tespit (tepe {peak})</span>
        <span>{formatTimestamp(durationMs)}</span>
      </div>
    </div>
  );
}
