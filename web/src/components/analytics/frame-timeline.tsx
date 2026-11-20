"use client";

import { useMemo, type KeyboardEvent, type MouseEvent } from "react";
import type { FrameDetections } from "@/lib/api/contract";
import { bucketFrames } from "@/lib/detections/utils";
import { formatTimestamp } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

interface Props {
  frames: readonly FrameDetections[];
  durationMs: number;
  threshold: number;
  /** Oynatma konumu; verilmezse imleç çizilmez. */
  playheadMs?: number;
  onSeek?: (ms: number) => void;
  height?: number;
  /** Alt satırdaki açıklama. */
  caption?: string;
}

/**
 * Tespit zaman çizelgesi: her çubuk, o zaman diliminde eşik üstü EN YÜKSEK kare başına tespit sayısıdır.
 * Analiz edilmemiş aralık ince çizgiyle ("veri yok"), sıfır tespit daha belirgin taban çizgisiyle ayrılır.
 * Oynatma imleci koyu turuncu (zaman rolü).
 */
export function FrameTimeline({ frames, durationMs, threshold, playheadMs, onSeek, height = 44, caption }: Props) {
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
    else if (e.key === "Home") onSeek(0);
    else if (e.key === "End") onSeek(durationMs);
    else return;
    e.preventDefault();
  };

  return (
    <div className="min-w-0">
      <div
        className={cx(
          "group relative flex items-end gap-px rounded-lg border border-line bg-deep/80 px-1.5 py-1 transition-colors duration-200",
          interactive && "cursor-pointer hover:border-line-strong",
        )}
        style={{ height }}
        onClick={seekFromX}
        role={interactive ? "slider" : "img"}
        tabIndex={interactive ? 0 : undefined}
        onKeyDown={onKey}
        aria-label={interactive ? "Tespit zaman çizelgesi; konuma gitmek için tıklayın veya ok tuşlarını kullanın" : "Tespit zaman çizelgesi"}
        aria-valuemin={interactive ? 0 : undefined}
        aria-valuemax={interactive ? Math.round(durationMs) : undefined}
        aria-valuenow={interactive ? Math.round(playheadMs ?? 0) : undefined}
        aria-valuetext={interactive ? formatTimestamp(playheadMs ?? 0) : undefined}
      >
        {buckets.map((b, i) => (
          <div key={i} className="flex h-full flex-1 items-end" title={b.analyzed ? `${formatTimestamp(b.startMs)} · en çok ${b.peak} tespit` : `${formatTimestamp(b.startMs)} · analiz edilmedi`}>
            {b.analyzed ? (
              <div
                className={b.peak > 0 ? "w-full rounded-t-[1px] bg-cyan/75 transition-[height] duration-200" : "h-[2px] w-full bg-line-strong"}
                style={b.peak > 0 ? { height: `${Math.max(10, (b.peak / peak) * 100)}%` } : undefined}
              />
            ) : (
              <div className="h-px w-full bg-line" />
            )}
          </div>
        ))}
        {playheadMs !== undefined && durationMs > 0 && (
          <div aria-hidden className="pointer-events-none absolute -bottom-1 -top-1 w-0.5 -translate-x-1/2 bg-orange" style={{ left: `${Math.min(100, (playheadMs / durationMs) * 100)}%` }}>
            <span className="absolute -left-[4px] -top-[5px] size-2.5 rotate-45 rounded-[2px] bg-orange" />
          </div>
        )}
      </div>
      <div className="tnum mt-1.5 flex justify-between gap-2 font-mono text-xs text-subtle">
        <span>{formatTimestamp(0)}</span>
        <span className="truncate font-sans">{caption ?? `Çubuk: kare başına en çok eşik üstü tespit (tepe ${peak})`}</span>
        <span>{formatTimestamp(durationMs)}</span>
      </div>
    </div>
  );
}
