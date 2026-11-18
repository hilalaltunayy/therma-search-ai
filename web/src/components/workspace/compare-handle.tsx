"use client";

import { useRef, type KeyboardEvent, type PointerEvent } from "react";

/** Orijinal/işlenmiş karşılaştırma ayırıcısı. Fare/dokunma sürükleme + klavye (←/→, Home/End). */
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
      className="absolute inset-0 z-10 touch-none"
      onPointerDown={(e) => {
        dragging.current = true;
        e.currentTarget.setPointerCapture(e.pointerId);
        fromEvent(e);
      }}
      onPointerMove={(e) => dragging.current && fromEvent(e)}
      onPointerUp={() => (dragging.current = false)}
      onPointerCancel={() => (dragging.current = false)}
    >
      <div className="absolute inset-y-0 w-px bg-white/80" style={{ left: `${value}%` }} />
      <div
        role="slider"
        tabIndex={0}
        aria-label="Orijinal ve işlenmiş görüntü karşılaştırma ayırıcısı"
        aria-orientation="horizontal"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value)}
        aria-valuetext={`Orijinal %${Math.round(value)}, işlenmiş %${100 - Math.round(value)}`}
        onKeyDown={onKey}
        className="absolute top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize place-items-center rounded-full border border-white/70 bg-base/80 text-white backdrop-blur"
        style={{ left: `${value}%` }}
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M9 7l-5 5 5 5M15 7l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}
