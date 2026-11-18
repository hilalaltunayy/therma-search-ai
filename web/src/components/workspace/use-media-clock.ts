"use client";

import { useEffect, useState, type RefObject } from "react";

export interface MediaClock {
  timeMs: number;
  playing: boolean;
  durationMs: number;
}

/**
 * <video> öğesinin oynatma zamanını okur. Oynatma sırasında requestAnimationFrame ile akıcı güncellenir
 * (timeupdate ~4 Hz olduğu için kutular geriden gelirdi); duraklatma/aramada olaylarla eşitlenir.
 */
export function useMediaClock(ref: RefObject<HTMLVideoElement | null>, enabled: boolean): MediaClock {
  const [clock, setClock] = useState<MediaClock>({ timeMs: 0, playing: false, durationMs: 0 });

  useEffect(() => {
    const v = ref.current;
    if (!enabled || !v) return;
    let raf = 0;

    const read = () =>
      setClock((c) => {
        const timeMs = v.currentTime * 1000;
        const durationMs = Number.isFinite(v.duration) ? v.duration * 1000 : 0;
        const playing = !v.paused && !v.ended;
        return c.timeMs === timeMs && c.durationMs === durationMs && c.playing === playing ? c : { timeMs, durationMs, playing };
      });
    const loop = () => {
      read();
      raf = requestAnimationFrame(loop);
    };
    const onPlay = () => {
      cancelAnimationFrame(raf);
      loop();
    };
    const onStop = () => {
      cancelAnimationFrame(raf);
      read();
    };

    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onStop);
    v.addEventListener("ended", onStop);
    v.addEventListener("seeked", read);
    v.addEventListener("seeking", read);
    v.addEventListener("loadedmetadata", read);
    read();
    if (!v.paused) loop();

    return () => {
      cancelAnimationFrame(raf);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onStop);
      v.removeEventListener("ended", onStop);
      v.removeEventListener("seeked", read);
      v.removeEventListener("seeking", read);
      v.removeEventListener("loadedmetadata", read);
    };
  }, [ref, enabled]);

  return clock;
}
