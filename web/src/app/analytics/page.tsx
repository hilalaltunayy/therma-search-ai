"use client";

import Link from "next/link";
import { useMemo, type ReactNode } from "react";
import { Activity, BarChart3, Clock3, History, Layers, ScanSearch, TriangleAlert } from "lucide-react";
import { useAnalysis } from "@/state/analysis-store";
import { allDetections, filterByConfidence, summarizeFrames } from "@/lib/detections/utils";
import { formatConfidence, formatDurationMs, formatTimestamp } from "@/lib/format";
import { Badge, Button, DemoBadge, Eyebrow, GlassCard, GlassPanel, StateView, cx } from "@/components/ui/primitives";
import { ConfidenceHistogram } from "@/components/analytics/confidence-histogram";
import { FrameTimeline } from "@/components/analytics/frame-timeline";

function MetricCard({ icon, label, value, hint, tone }: { icon: ReactNode; label: string; value: ReactNode; hint?: string; tone?: "cyan" | "amber" }) {
  return (
    <GlassCard className="flex min-w-0 flex-col gap-3 p-4" tabIndex={0}>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>{label}</Eyebrow>
        <span className="grid size-8 place-items-center rounded-lg border border-line-strong bg-surface-2/80 text-subtle" aria-hidden>
          {icon}
        </span>
      </div>
      <p className={cx("tnum font-mono text-[30px] font-semibold leading-none", tone === "cyan" ? "text-cyan" : tone === "amber" ? "text-amber" : "text-ink")}>{value}</p>
      {hint && <p className="text-[13px] leading-snug text-subtle">{hint}</p>}
    </GlassCard>
  );
}

export default function AnalyticsPage() {
  const { state, threshold, setThreshold } = useAnalysis();
  const { result, phase, job, error, file } = state;
  const summary = useMemo(() => (result ? summarizeFrames(result.frames, threshold) : null), [result, threshold]);
  const detections = useMemo(() => (result ? allDetections(result.frames) : []), [result]);
  const above = useMemo(() => filterByConfidence(detections, threshold), [detections, threshold]);

  if (!result) {
    const busy = phase === "submitting" || phase === "processing";
    return (
      <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 p-4 lg:p-6">
        <GlassPanel>
          {phase === "failed" ? (
            <StateView role="alert" tone="danger" icon={<TriangleAlert className="size-6" aria-hidden />} title="Son analiz başarısız oldu" description={error?.message}
              action={<Link href="/workspace"><Button variant="primary">Çalışma alanına dön</Button></Link>} />
          ) : busy ? (
            <StateView role="status" tone="cyan" icon={<Activity className="size-6" aria-hidden />} title="Analiz sürüyor"
              description={`İş durumu: ${job?.status ?? "başlatılıyor"}. Sonuçlar tamamlandığında burada görünür.`} />
          ) : (
            <StateView icon={<BarChart3 className="size-6" aria-hidden />} title="Henüz analiz sonucu yok"
              description="Detection Workspace'te bir analiz tamamlandığında tespit sayıları, skor dağılımı ve kare zaman çizelgesi burada oluşur. Gerçek veri olmadan örnek değer gösterilmez."
              action={<Link href="/workspace"><Button variant="primary">Çalışma alanına git</Button></Link>} />
          )}
        </GlassPanel>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { icon: <Layers className="size-5" />, t: "Tespit özeti", d: "Toplam tespit (kare toplamı), kare başına tepe ve ortalama skor." },
            { icon: <BarChart3 className="size-5" />, t: "Skor dağılımı", d: "Eşik çizgisiyle birlikte 10 aralıklı histogram; eşiği buradan da ayarlayabilirsiniz." },
            { icon: <Clock3 className="size-5" />, t: "Kare zaman çizelgesi", d: "Videoda her zaman diliminde kaç tespit olduğu." },
          ].map((c) => (
            <GlassCard key={c.t} className="flex gap-3 p-4" tabIndex={0}>
              <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-dashed border-line-strong text-subtle" aria-hidden>{c.icon}</span>
              <span>
                <span className="block text-[15px] font-semibold text-ink">{c.t}</span>
                <span className="text-[13.5px] text-muted">{c.d}</span>
              </span>
            </GlassCard>
          ))}
        </div>
        <HistoryPlaceholder />
      </div>
    );
  }

  const isVideo = result.media.kind === "video";
  const mock = result.provenance === "mock";

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <Eyebrow>Son analiz</Eyebrow>
          <h2 className="truncate text-xl font-semibold text-ink">{file?.name}</h2>
          <p className="tnum font-mono text-[13px] text-subtle">
            {result.media.width}×{result.media.height} px{result.media.durationMs ? ` · ${formatTimestamp(result.media.durationMs)}` : ""} · {result.jobId}
          </p>
        </div>
        {mock && (
          <p role="note" className="flex max-w-xl items-center gap-2 rounded-xl border border-amber/35 bg-amber-soft px-3 py-2 text-[13.5px] text-amber">
            <DemoBadge /> Bu sayfadaki tüm değerler yapay demo verisinden hesaplanmıştır.
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard icon={<Layers className="size-4" />} label={isVideo ? "Toplam tespit" : "Tespit"} value={summary?.totalDetections ?? "—"} tone="cyan" hint={isVideo ? "Kare toplamı; benzersiz kişi sayısı değildir" : "Eşik üstü"} />
        <MetricCard icon={<ScanSearch className="size-4" />} label="Kare başına tepe" value={summary?.peakDetectionsPerFrame ?? "—"} hint="Tek karedeki en çok eşik üstü tespit" />
        <MetricCard icon={<Activity className="size-4" />} label="Ortalama skor" value={summary?.meanConfidence == null ? "—" : formatConfidence(summary.meanConfidence)} hint="Eşik üstü tespitler; kalibre olasılık değil" />
        <MetricCard icon={<BarChart3 className="size-4" />} label="Analiz edilen kare" value={summary?.framesAnalyzed ?? "—"} hint={summary ? `${summary.framesWithDetections} karede eşik üstü tespit var` : undefined} />
        <MetricCard icon={<Clock3 className="size-4" />} label="Analiz süresi" value={formatDurationMs(result.timing.processingMs)} hint={result.timing.measured ? "Backend ölçümü" : "Simülasyon süresi (ölçüm değil)"} tone={result.timing.measured ? undefined : "amber"} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <GlassPanel title="Güven skoru dağılımı" aside={<span className="tnum">{detections.length} tespit · eşik öncesi</span>}>
          <div className="pt-4">
            <ConfidenceHistogram detections={detections} threshold={threshold} />
          </div>
          <div className="mt-5 flex items-center gap-4 border-t border-line pt-4">
            <label htmlFor="an-threshold" className="shrink-0 text-sm text-muted">Güven eşiği</label>
            <input id="an-threshold" type="range" className="range min-w-0 flex-1" min={0} max={1} step={0.01} value={threshold}
              style={{ ["--fill" as string]: `${threshold * 100}%` }}
              onChange={(e) => setThreshold(Math.max(result.minConfidenceApplied, Number(e.target.value)))}
              aria-valuetext={`${threshold.toFixed(2)} ve üzeri skorlar gösterilir`} />
            <output htmlFor="an-threshold" className="tnum w-12 text-right font-mono text-lg font-semibold text-cyan">{threshold.toFixed(2)}</output>
          </div>
          <p className="tnum mt-2 text-[13px] text-subtle">Eşik üstü: {above.length} / {detections.length} · yalnızca görüntüleme filtresi</p>
        </GlassPanel>

        <GlassPanel title="İşlem durumu" aside={<Badge tone="cyan">Tamamlandı</Badge>}>
          <dl className="divide-y divide-line text-sm">
            {(
              [
                ["Kaynak", mock ? "Mock üretici (model yok)" : "Model çıktısı"],
                ["Model", `${result.model.name}${result.model.version ? ` · ${result.model.version}` : ""}`],
                ["Sınıflar", result.model.classes.map((c) => c.name).join(", ") || "—"],
                ["Sunucu skor tabanı", result.minConfidenceApplied.toFixed(2)],
                ["Kare adımı", isVideo ? `her ${result.frameStride}. kare` : "—"],
                ["İşlem süresi", `${formatDurationMs(result.timing.processingMs)}${result.timing.measured ? "" : " · simülasyon"}`],
              ] as const
            ).map(([k, v]) => (
              <div key={k} className="flex items-baseline justify-between gap-4 py-2.5">
                <dt className="text-subtle">{k}</dt>
                <dd className="tnum text-right font-mono text-[13.5px] text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </GlassPanel>
      </div>

      <GlassPanel title="Video kareleri · zaman çizelgesi" aside={isVideo ? <span className="tnum">{result.frames.length} analiz edilen kare</span> : undefined}>
        {isVideo ? (
          <FrameTimeline frames={result.frames} durationMs={result.media.durationMs ?? 0} threshold={threshold} height={96} caption={mock ? "Kare başına eşik üstü tespit · DEMO" : undefined} />
        ) : (
          <p className="text-sm text-muted">Bu analiz tek bir görüntüdür; zaman çizelgesi yalnızca video sonuçlarında oluşur.</p>
        )}
      </GlassPanel>

      <HistoryPlaceholder />
    </div>
  );
}

function HistoryPlaceholder() {
  return (
    <GlassPanel title="Analiz geçmişi" aside={<Badge>Planlı</Badge>}>
      <div className="flex items-start gap-3 text-sm leading-relaxed text-muted">
        <History className="mt-0.5 size-5 shrink-0 text-subtle" aria-hidden />
        <p>
          Geçmiş analizler için kalıcı depolama henüz yok; yalnızca geçerli oturumdaki son analiz tutulur ve sayfa yenilenince kaybolur. Backend hazır olduğunda geçmiş, iş listesi uç noktasıyla eklenecek (docs/api-contract.md, “Açık kararlar”).
        </p>
      </div>
    </GlassPanel>
  );
}
