import type { Metadata } from "next";
import { Info } from "lucide-react";
import { SAR_MODULES } from "@/features/sar-modules/registry";
import { PlannedCard } from "@/components/ui/planned-card";

export const metadata: Metadata = { title: "Search & Rescue" };

export default function OperationsPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 p-4 lg:p-6">
      <div role="note" className="glass glass-edge flex items-start gap-3 rounded-2xl px-5 py-4 text-sm leading-relaxed text-muted">
        <Info className="mt-0.5 size-5 shrink-0 text-cyan" aria-hidden />
        <p>
          Bu modüller <strong className="font-semibold text-ink">henüz geliştirilmedi</strong> (ikinci dönem). Gerçek GPS, risk puanı, rota veya ekip verisi
          olmadığından bu sayfada hiçbir koordinat, harita, puan ya da ekip bilgisi gösterilmez. Her kart, modülün çalışması için gereken veriyi listeler.
        </p>
      </div>
      <ul className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {SAR_MODULES.map((m) => (
          <li key={m.id}>
            <PlannedCard icon={m.icon} title={m.title} description={m.description} listTitle="Gerekli veri ve kararlar" items={m.requires} />
          </li>
        ))}
      </ul>
    </div>
  );
}
