import type { Detection, MediaInfo } from "@/lib/api/contract";
import { bandOf, boxToPercent, type ConfidenceBand } from "@/lib/detections/utils";
import { formatConfidence } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

/**
 * Tespit kutusu katmanı — medya öğesinden ayrı, saf sunum katmanı.
 * Girdi: piksel uzayındaki kutular (docs/api-contract.md). Çıktı: yüzde konumlu DOM kutuları;
 * bu sayede medya hangi boyutta gösterilirse gösterilsin kutular hizalı kalır.
 */

const bandStyles: Record<ConfidenceBand, { box: string; chip: string }> = {
  high: { box: "border-accent shadow-[0_0_0_1px_rgb(34_211_238/0.35)]", chip: "bg-accent text-base" },
  medium: { box: "border-electric shadow-[0_0_0_1px_rgb(79_140_255/0.35)]", chip: "bg-electric text-base" },
  low: { box: "border-warn shadow-[0_0_0_1px_rgb(245_158_11/0.35)]", chip: "bg-warn text-base" },
};

interface Props {
  detections: readonly Detection[];
  media: Pick<MediaInfo, "width" | "height">;
  showLabels: boolean;
  selectedId: string | null;
}

export function DetectionOverlay({ detections, media, showLabels, selectedId }: Props) {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      {detections.map((d) => {
        const p = boxToPercent(d.box, media);
        const style = bandStyles[bandOf(d.confidence)];
        const selected = d.id === selectedId;
        const labelBelow = p.top < 7;
        return (
          <div
            key={d.id}
            className={cx(
              "absolute border-[1.5px] transition-[border-color,box-shadow] duration-150",
              style.box,
              selected && "!border-white ring-2 ring-white/60",
            )}
            style={{ left: `${p.left}%`, top: `${p.top}%`, width: `${p.width}%`, height: `${p.height}%` }}
          >
            {showLabels && (
              <span
                className={cx(
                  "tnum absolute whitespace-nowrap rounded-sm px-1 py-px text-[10px] font-semibold leading-4",
                  labelBelow ? "top-full" : "bottom-full",
                  p.left > 78 ? "right-[-1.5px]" : "left-[-1.5px]",
                  style.chip,
                )}
              >
                {d.className} {formatConfidence(d.confidence)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
