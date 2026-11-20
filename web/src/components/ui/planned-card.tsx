import type { LucideIcon } from "lucide-react";
import { Badge, GlassCard } from "@/components/ui/primitives";

/**
 * Planlı modül kartı: buzlu cam yüzey + hafif topoğrafik doku + hover yansıması.
 * Etkileşim yalnızca görseldir; kart bir işlev başlatmaz ve veri göstermez.
 */
export function PlannedCard({
  icon: Icon,
  title,
  description,
  listTitle,
  items,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  listTitle: string;
  items: readonly string[];
}) {
  return (
    <GlassCard tabIndex={0} aria-label={`${title}, planlı modül`} className="group flex h-full flex-col overflow-hidden rounded-2xl p-5">
      {/* Topoğrafik doku: eş yükselti halkaları (dekoratif, veri değil) */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-60 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          backgroundImage:
            "repeating-radial-gradient(circle at 85% 0%, transparent 0 18px, rgb(163 177 198 / 0.07) 18px 19px), repeating-radial-gradient(circle at 0% 100%, transparent 0 26px, rgb(163 177 198 / 0.05) 26px 27px)",
        }}
      />
      <div className="flex items-start justify-between gap-3">
        <span className="grid size-12 place-items-center rounded-xl border border-line-strong bg-surface-2/70 text-muted transition-[color,border-color,background-color] duration-200 group-hover:border-cyan/40 group-hover:text-cyan">
          <Icon className="size-6" aria-hidden />
        </span>
        <Badge>Planlı · veri yok</Badge>
      </div>
      <h3 className="mt-4 text-[17px] font-semibold text-ink">{title}</h3>
      <p className="mt-1 text-sm leading-relaxed text-muted">{description}</p>
      <p className="mb-2 mt-5 text-xs font-semibold uppercase tracking-[0.1em] text-subtle">{listTitle}</p>
      <ul className="space-y-1.5 text-[13.5px] text-muted">
        {items.map((r) => (
          <li key={r} className="flex gap-2.5">
            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-violet/70" />
            {r}
          </li>
        ))}
      </ul>
    </GlassCard>
  );
}
