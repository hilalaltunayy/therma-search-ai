"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { MediaInfo } from "@/lib/api/contract";
import { bandOf, boxToPercent } from "@/lib/detections/utils";
import { estimateLabelWidth, placeLabels } from "@/lib/detections/labels";
import { formatConfidence } from "@/lib/format";
import { cx } from "@/components/ui/primitives";
import type { RankedDetection } from "./ranked";

/**
 * Tespit katmanı — medyadan ayrı sunum katmanı.
 * Girdi: orijinal piksel uzayındaki kutular (docs/api-contract.md). Kutular yüzde konumla çizilir;
 * etiketler ekran pikselinde çakışmasız yerleştirilir (lib/detections/labels.ts).
 * Durumlar: normal (cyan), düşük skor (kesikli cyan), hover (açık cyan + kalın), seçili (violet + halka).
 * Görüntü pikselleri değiştirilmez.
 */

const LABEL_H = 20;

interface Props {
  items: readonly RankedDetection[];
  media: Pick<MediaInfo, "width" | "height">;
  showLabels: boolean;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  /** Karşılaştır modunda kutular tıklanamaz (ayırıcı sürükleme önceliklidir). */
  interactive: boolean;
}

export function DetectionOverlay({ items, media, showLabels, selectedId, hoveredId, onSelect, onHover, interactive }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      if (entry) setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const labels = useMemo(() => {
    if (!showLabels || size.width === 0) return new Map<string, { left: number; top: number }>();
    const sx = size.width / media.width;
    const sy = size.height / media.height;
    const placed = placeLabels(
      items.map(({ detection: d, rank }) => ({
        id: d.id,
        x: d.box.x * sx,
        y: d.box.y * sy,
        w: d.box.width * sx,
        h: d.box.height * sy,
        lw: estimateLabelWidth(`#${rank} ${formatConfidence(d.confidence)}`),
        lh: LABEL_H,
        priority: d.id === selectedId ? 2 : d.confidence,
      })),
      size,
    );
    return new Map(placed.map((p) => [p.id, p]));
  }, [items, media.width, media.height, size, showLabels, selectedId]);

  return (
    <div ref={ref} className="absolute inset-0">
      {items.map(({ detection: d, rank }) => {
        const p = boxToPercent(d.box, media);
        const selected = d.id === selectedId;
        const hovered = !selected && d.id === hoveredId;
        const low = bandOf(d.confidence) === "low";
        return (
          <button
            key={d.id}
            type="button"
            tabIndex={interactive ? 0 : -1}
            aria-pressed={selected}
            aria-label={`Tespit #${rank}, ${d.className}, skor ${formatConfidence(d.confidence)}`}
            onClick={() => onSelect(selected ? null : d.id)}
            onPointerEnter={() => onHover(d.id)}
            onPointerLeave={() => onHover(null)}
            onFocus={() => onHover(d.id)}
            onBlur={() => onHover(null)}
            className={cx(
              "absolute rounded-[2px] transition-[border-color,box-shadow,border-width] duration-150 ease-out focus-visible:outline-offset-4",
              interactive ? "cursor-pointer" : "pointer-events-none",
              selected
                ? "z-20 border-2 border-violet shadow-[0_0_0_1px_rgb(4_7_13/0.85),0_0_0_4px_rgb(117_86_184/0.38)]"
                : hovered
                  ? "z-10 border-2 border-[#7fe6f0] shadow-[0_0_0_1px_rgb(4_7_13/0.85),0_0_0_3px_rgb(34_201_217/0.25)]"
                  : cx("border-[1.5px] border-cyan shadow-[0_0_0_1px_rgb(4_7_13/0.75)]", low && "border-dashed"),
            )}
            style={{ left: `${p.left}%`, top: `${p.top}%`, width: `${p.width}%`, height: `${p.height}%` }}
          />
        );
      })}
      {showLabels &&
        items.map(({ detection: d, rank }) => {
          const pos = labels.get(d.id);
          if (!pos) return null;
          const selected = d.id === selectedId;
          const hovered = !selected && d.id === hoveredId;
          const low = bandOf(d.confidence) === "low";
          return (
            <span
              key={`l-${d.id}`}
              aria-hidden
              className={cx(
                "tnum pointer-events-none absolute flex items-center whitespace-nowrap rounded-[5px] px-1.5 font-mono text-xs font-semibold leading-none transition-colors duration-150",
                selected
                  ? "z-30 bg-violet text-[#160E2A]"
                  : hovered
                    ? "z-20 bg-[#7fe6f0] text-[#04121A]"
                    : low
                      ? "z-10 bg-deep/90 text-cyan shadow-[inset_0_0_0_1px_rgb(34_201_217/0.6)]"
                      : "z-10 bg-cyan text-[#04121A]",
              )}
              style={{ left: pos.left, top: pos.top, height: LABEL_H }}
            >
              #{rank}&nbsp;{formatConfidence(d.confidence)}
            </span>
          );
        })}
    </div>
  );
}
