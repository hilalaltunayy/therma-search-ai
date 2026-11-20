"use client";

import { useRef, type KeyboardEvent, type PointerEvent } from "react";

/** Orijinal / tespitli karşılaştırma ayırıcısı. Fare/dokunma sürükleme + klavye (←/→, Shift ile 10, Home/End). */
export function CompareHandle({ value, onChange }: { value: number; onChange: (pct: number) => void }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const fromEvent = (e: PointerEvent) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect) return;
    onChange(Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)));
  };

  const onKey = (e: KeyboardEvent) => {
    const step = e.shiftKey ? 10 : 2;
    if (e.key === "ArrowLeft") onChange(Math.max(0, value - step));
    else if (e.key === "ArrowRight") onChange(Math.min(100, value + step));
    else if (e.key === "Home") onChange(0);
    else if (e.key === "End") onChange(100);
    else return;
    e.preventDefault();
  };

  return (
    <div
      ref={trackRef}
      className="absolute inset-0 z-30 cursor-ew-resize touch-none"
      onPointerDown={(e) => {
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        fromEvent(e);
      }}
      onPointerMove={(e) => dragging.current && fromEvent(e)}
      onPointerUp={() => (dragging.current = false)}
      onPointerCancel={() => (dragging.current = false)}
    >
      <div className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-ink/90 shadow-[0_0_0_1px_rgb(4_7_13/0.6)]" style={{ left: `${value}%` }} />
      <div
        role="slider"
        tabIndex={0}
        aria-label="Orijinal ve tespitli görünüm karşılaştırma ayırıcısı"
        aria-orientation="horizontal"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value)}
        aria-valuetext={`Orijinal yüzde ${Math.round(value)}, tespitli yüzde ${100 - Math.round(value)}`}
        onKeyDown={onKey}
        className="hud-chip absolute top-1/2 grid size-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full p-0 text-ink transition-transform duration-150 hover:scale-105"
        style={{ left: `${value}%` }}
      >
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M9 7l-5 5 5 5M15 7l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
