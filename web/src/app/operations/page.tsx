import type { Metadata } from "next";
import { Info } from "lucide-react";
import { SAR_MODULES } from "@/features/sar-modules/registry";
import { Badge, Panel } from "@/components/ui/primitives";

export const metadata: Metadata = { title: "Search & Rescue" };

export default function OperationsPage() {
  return (
    <div className="space-y-4">
      <div role="note" className="flex items-start gap-3 rounded-lg border border-line-strong bg-raised px-4 py-3 text-[13px] leading-relaxed text-muted">
        <Info className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
        <p>
          Bu modüller <strong className="text-ink">henüz geliştirilmedi</strong> (ikinci dönem). Gerçek GPS, risk puanı veya operasyon verisi bulunmadığından
          bu sayfada hiçbir koordinat, harita, puan ya da ekip bilgisi gösterilmez. Her kart, modülün çalışması için gereken veriyi listeler.
        </p>
      </div>

      <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {SAR_MODULES.map((m) => {
          const Icon = m.icon;
          return (
            <li key={m.id}>
              <Panel className="h-full" title={m.title} aside={<Badge>Planlı · veri yok</Badge>}>
                <div className="flex gap-3">
                  <div className="grid size-10 shrink-0 place-items-center rounded-lg border border-line-strong bg-raised text-subtle">
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <p className="text-[13px] leading-relaxed text-muted">{m.description}</p>
                </div>
                <p className="mb-1.5 mt-4 text-[11px] uppercase tracking-[0.08em] text-subtle">Gerekli veri / kararlar</p>
                <ul className="space-y-1 text-xs text-muted">
                  {m.requires.map((r) => (
                    <li key={r} className="flex gap-2"><span aria-hidden className="mt-1.5 size-1 shrink-0 rounded-full bg-line-strong" />{r}</li>
                  ))}
                </ul>
              </Panel>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
