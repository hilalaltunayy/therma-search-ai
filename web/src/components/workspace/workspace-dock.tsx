"use client";

import { useState, type RefObject } from "react";
import { FastForward, Image as ImageIcon, Pause, Play, Rewind } from "lucide-react";
import type { AnalysisResult, MediaKind } from "@/lib/api/contract";
import { formatTimestamp } from "@/lib/format";
import { IconButton, Segmented } from "@/components/ui/primitives";
import { FrameTimeline } from "@/components/analytics/frame-timeline";
import type { MediaClock } from "./use-media-clock";

interface Props {
  kind: MediaKind | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  clock: MediaClock;
  result: AnalysisResult | null;
  threshold: number;
}

/**
 * Sabit oynatıcı paneli: Workspace'in en altında, görüntü alanıyla aynı sütunda.
 * Masaüstünde yükseklik sabittir; kare küçülür, oynatıcı aşağı kaymaz.
 */
export function WorkspaceDock({ kind, videoRef, clock, result, threshold }: Props) {
  const [rate, setRate] = useState("1");
  const v = videoRef.current;

  if (kind !== "video") {
    return (
      <div className="flex min-h-[60px] items-center gap-3 rounded-2xl border border-line bg-surface-2/80 px-4 text-sm text-subtle">
        <ImageIcon className="size-4 shrink-0" aria-hidden />
        {kind === "image"
          ? "Tek kare görüntü: oynatıcı ve zaman çizelgesi yalnızca video için kullanılır."
          : "Video yüklendiğinde oynatıcı ve tespit zaman çizelgesi burada sabit kalır."}
      </div>
    );
  }

  const duration = clock.durationMs;
  const seekBy = (sec: number) => {
    if (v) v.currentTime = Math.min(Math.max(0, v.currentTime + sec), v.duration || 0);
  };
  const toggle = () => {
    if (!v) return;
    if (v.paused) void v.play();
    else v.pause();
  };

  return (
    <div className="grid items-center gap-x-4 gap-y-3 rounded-2xl border border-line bg-surface-2/80 px-3 py-3 sm:px-4 md:grid-cols-[auto_auto_minmax(0,1fr)_auto]">
      <div className="flex items-center gap-1.5">
        <IconButton label="5 saniye geri" side="top" onClick={() => seekBy(-5)}>
          <Rewind className="size-4" />
        </IconButton>
        <button
          type="button"
          aria-label={clock.playing ? "Duraklat" : "Oynat"}
          onClick={toggle}
          className="grid size-11 place-items-center rounded-xl bg-cyan text-[#04121A] shadow-[0_6px_18px_-8px_rgb(34_201_217/0.6)] transition-[background-color,transform,box-shadow] duration-200 hover:bg-[#3fd6e4] active:scale-95"
        >
          {clock.playing ? <Pause className="size-5" /> : <Play className="size-5" />}
        </button>
        <IconButton label="5 saniye ileri" side="top" onClick={() => seekBy(5)}>
          <FastForward className="size-4" />
        </IconButton>
        <span className="tnum ml-2 whitespace-nowrap font-mono text-sm text-muted md:hidden">
          <span className="font-semibold text-orange-text">{formatTimestamp(clock.timeMs)}</span> / {formatTimestamp(duration)}
        </span>
      </div>
      <span className="tnum hidden whitespace-nowrap font-mono text-sm text-muted md:inline">
        <span className="font-semibold text-orange-text">{formatTimestamp(clock.timeMs)}</span> / {formatTimestamp(duration)}
      </span>
      {result ? (
        <FrameTimeline
          frames={result.frames}
          durationMs={result.media.durationMs ?? duration}
          threshold={threshold}
          playheadMs={clock.timeMs}
          onSeek={(ms) => {
            if (videoRef.current) videoRef.current.currentTime = ms / 1000;
          }}
          caption={result.provenance === "mock" ? "Kare başına eşik üstü tespit · DEMO" : undefined}
        />
      ) : (
        <div className="min-w-0">
          <input
            type="range"
            className="range fill-left w-full"
            aria-label="Video konumu"
            min={0}
            max={Math.max(duration, 1)}
            step={10}
            value={Math.min(clock.timeMs, Math.max(duration, 1))}
            style={{ ["--fill" as string]: `${duration ? (clock.timeMs / duration) * 100 : 0}%` }}
            onChange={(e) => {
              if (v) v.currentTime = Number(e.target.value) / 1000;
            }}
          />
          <p className="mt-1 text-xs text-subtle">Tespit zaman çizelgesi analizden sonra dolar.</p>
        </div>
      )}
      <Segmented
        label="Oynatma hızı"
        value={rate}
        className="justify-self-start md:justify-self-end"
        onChange={(r) => {
          setRate(r);
          if (v) v.playbackRate = Number(r);
        }}
        options={[
          { value: "0.5", label: "0.5×" },
          { value: "1", label: "1×" },
          { value: "2", label: "2×" },
        ]}
      />
    </div>
  );
}
