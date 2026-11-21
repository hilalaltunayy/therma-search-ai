import type { Metadata } from "next";
import { FlaskConical } from "lucide-react";
import { LAB_SECTIONS } from "@/features/lab/registry";
import { PlannedCard } from "@/components/ui/planned-card";

export const metadata: Metadata = { title: "Model & Dataset Lab" };

export default function LabPage() {
  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 p-4 lg:p-6">
      <div role="note" className="glass glass-edge flex items-start gap-3 rounded-2xl px-5 py-4 text-sm leading-relaxed text-muted">
        <FlaskConical className="mt-0.5 size-5 shrink-0 text-violet" aria-hidden />
        <p>
          Model &amp; Dataset Lab, eğitim ve değerlendirme sonuçları için ayrı bir <strong className="font-semibold text-ink">mühendislik modülüdür</strong> ve henüz
          geliştirilmedi. Model metrikleri Detection Workspace&apos;e taşınmaz. Kaynak raporlar bağlanana kadar burada hiçbir sayı, metrik veya grafik gösterilmez;
          her kart beslenmesi gereken gerçek kaynağı listeler.
        </p>
      </div>
      <ul className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {LAB_SECTIONS.map((s) => (
          <li key={s.id}>
            <PlannedCard icon={s.icon} title={s.title} description={s.description} listTitle="Beklenen kaynak" items={[s.source]} />
          </li>
        ))}
      </ul>
    </div>
  );
}
