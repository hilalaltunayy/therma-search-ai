"use client";

import { useState, type RefObject } from "react";
import { Pause, Play, Rewind, FastForward } from "lucide-react";
import { formatTimestamp } from "@/lib/format";
import { Button, Segmented } from "@/components/ui/primitives";
import type { MediaClock } from "./use-media-clock";

export function PlayerControls({ videoRef, clock }: { videoRef: RefObject<HTMLVideoElement | null>; clock: MediaClock }) {
  const v = videoRef.current;
  const [rate, setRate] = useState("1");
  const seekBy = (sec: number) => {
    if (v) v.currentTime = Math.min(Math.max(0, v.currentTime + sec), v.duration || 0);
  };
  const toggle = () => {
    if (!v) return;
    if (v.paused) void v.play();
    else v.pause();
  };
  const duration = clock.durationMs;

  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-3">
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" aria-label="5 saniye geri" onClick={() => seekBy(-5)}>
          <Rewind className="size-4" aria-hidden />
        </Button>
        <Button variant="secondary" size="sm" aria-label={clock.playing ? "Duraklat" : "Oynat"} onClick={toggle} className="w-10">
          {clock.playing ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
        </Button>
        <Button variant="ghost" size="sm" aria-label="5 saniye ileri" onClick={() => seekBy(5)}>
          <FastForward className="size-4" aria-hidden />
        </Button>
      </div>
      <span className="tnum shrink-0 whitespace-nowrap font-mono text-xs text-muted">
        {formatTimestamp(clock.timeMs)} / {formatTimestamp(duration)}
      </span>
      <input
        type="range"
        className="range min-w-32 flex-1"
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
      <Segmented
        label="Oynatma hızı"
        value={rate}
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
