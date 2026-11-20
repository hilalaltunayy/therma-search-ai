import type { Detection } from "@/lib/api/contract";
import { bandOf, confidenceHistogram } from "@/lib/detections/utils";
import { cx } from "@/components/ui/primitives";

/** Tam sayı eksen üst sınırı (en az 2, ikiye bölünebilir ki orta çizgi tam sayı olsun). */
function niceMax(n: number): number {
  if (n <= 2) return 2;
  if (n <= 10) return n % 2 === 0 ? n : n + 1;
  const pow = 10 ** Math.floor(Math.log10(n));
  const steps = [1, 2, 2.5, 5, 10];
  for (const s of steps) if (s * pow >= n) return s * pow;
  return 10 * pow;
}

/**
 * Skor dağılımı (10 eşit aralık, eşik öncesi tüm tespitler).
 * Y ekseni: tespit sayısı (ızgara çizgileriyle); eşik çizgisi gösterim filtresini işaretler.
 * Erişilebilirlik: çubukların yanında tam sayı tablosu (sr-only).
 */
export function ConfidenceHistogram({ detections, threshold, height = 220 }: { detections: readonly Detection[]; threshold: number; height?: number }) {
  const bins = confidenceHistogram(detections, 10);
  const top = niceMax(Math.max(...bins.map((b) => b.count)));
  const ticks = [top, top / 2, 0];
  return (
    <figure className="min-w-0">
      <div className="flex gap-3 pt-7">
        <div className="tnum flex shrink-0 flex-col justify-between pb-[1px] text-right font-mono text-xs text-subtle" style={{ height }} aria-hidden>
          {ticks.map((t) => (
            <span key={t} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">{t}</span>
          ))}
        </div>
        <div className="relative min-w-0 flex-1" style={{ height }} role="img" aria-label="Güven skoru dağılımı histogramı">
          {ticks.map((t, i) => (
            <div key={t} aria-hidden className={cx("absolute inset-x-0 border-t", i === ticks.length - 1 ? "border-line-strong" : "border-dashed border-line")} style={{ top: `${(i / (ticks.length - 1)) * 100}%` }} />
          ))}
          <div className="absolute inset-0 flex items-end gap-2 px-1">
            {bins.map((b) => {
              const below = b.to <= threshold + 1e-9;
              const band = bandOf((b.from + b.to) / 2);
              return (
                <div key={b.from} className="group relative flex h-full flex-1 flex-col justify-end">
                  {b.count > 0 && (
                    <span className={cx("tnum mb-1 text-center font-mono text-xs", below ? "text-subtle" : "text-ink")}>{b.count}</span>
                  )}
                  <div
                    className={cx(
                      "w-full rounded-t-md transition-[height,background-color] duration-300 ease-out",
                      below ? "bg-line-strong" : band === "low" ? "bg-cyan/50 group-hover:bg-cyan/70" : band === "medium" ? "bg-cyan/75 group-hover:bg-cyan/90" : "bg-cyan group-hover:bg-[#5ee0ec]",
                    )}
                    style={{ height: `${(b.count / top) * 100}%`, minHeight: b.count ? 3 : 0 }}
                  />
                </div>
              );
            })}
          </div>
          <div aria-hidden className="pointer-events-none absolute -top-7 bottom-0 border-l-2 border-dashed border-violet/80" style={{ left: `${threshold * 100}%` }}>
            <span className={`tnum absolute top-0 whitespace-nowrap rounded bg-violet-soft px-1.5 py-0.5 font-mono text-xs text-violet ${threshold > 0.85 ? "right-1" : "left-1"}`}>eşik {threshold.toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div className="tnum ml-9 mt-2 flex justify-between px-1 font-mono text-xs text-subtle" aria-hidden>
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((v) => (
          <span key={v}>{v.toFixed(1)}</span>
        ))}
      </div>
      <figcaption className="mt-3 text-[13px] text-subtle">
        X: model skoru (kalibre olasılık değil) · Y: tespit sayısı · Gri çubuklar eşiğin altında kalır ve görüntüde gösterilmez.
      </figcaption>
      <table className="sr-only">
        <caption>Skor aralığına göre tespit sayıları</caption>
        <thead>
          <tr>
            <th>Aralık</th>
            <th>Sayı</th>
          </tr>
        </thead>
        <tbody>
          {bins.map((b) => (
            <tr key={b.from}>
              <td>
                {b.from.toFixed(1)}–{b.to.toFixed(1)}
              </td>
              <td>{b.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
