import type { Detection } from "@/lib/api/contract";
import { bandOf, confidenceHistogram } from "@/lib/detections/utils";
import { cx } from "@/components/ui/primitives";

const barColor = { high: "bg-accent", medium: "bg-electric", low: "bg-warn" } as const;

/**
 * Skor dağılımı: 10 eşit aralık. Eşik çizgisi gösterim filtresini işaret eder.
 * Erişilebilirlik: görsel çubukların yanında tam sayı tablosu (sr-only) bulunur.
 */
export function ConfidenceHistogram({ detections, threshold }: { detections: readonly Detection[]; threshold: number }) {
  const bins = confidenceHistogram(detections, 10);
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <figure>
      <div className="relative flex h-40 items-end gap-1.5 border-b border-line-strong px-1" role="img" aria-label="Güven skoru dağılımı histogramı">
        {bins.map((b) => (
          <div key={b.from} className="group relative flex h-full flex-1 flex-col justify-end">
            <span className="tnum mb-1 text-center text-[10px] text-muted">{b.count || ""}</span>
            <div
              className={cx("w-full rounded-t-sm transition-[height] duration-500", barColor[bandOf((b.from + b.to) / 2)], b.to <= threshold && "opacity-30")}
              style={{ height: `${(b.count / max) * 100}%`, minHeight: b.count ? 3 : 0 }}
            />
          </div>
        ))}
        <div
          aria-hidden
          className="absolute inset-y-0 border-l border-dashed border-white/60"
          style={{ left: `calc(${threshold * 100}% * (1 - 0.01) + 0.25rem)` }}
        />
      </div>
      <div className="tnum mt-1.5 flex justify-between px-1 text-[10px] text-subtle">
        <span>0.0</span><span>0.5</span><span>1.0</span>
      </div>
      <figcaption className="mt-2 text-[11px] text-subtle">Soluk çubuklar gösterim eşiğinin altındadır. Renkler yalnızca görsel banttır.</figcaption>
      <table className="sr-only">
        <caption>Skor aralığına göre tespit sayıları</caption>
        <thead><tr><th>Aralık</th><th>Sayı</th></tr></thead>
        <tbody>
          {bins.map((b) => (
            <tr key={b.from}><td>{b.from.toFixed(1)}–{b.to.toFixed(1)}</td><td>{b.count}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
