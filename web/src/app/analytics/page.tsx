"use client";

import Link from "next/link";
import { useMemo } from "react";
import { BarChart3, History, TriangleAlert } from "lucide-react";
import { useAnalysis } from "@/state/analysis-store";
import { allDetections, filterByConfidence, summarizeFrames } from "@/lib/detections/utils";
import { formatConfidence, formatDurationMs, formatTimestamp } from "@/lib/format";
import { Badge, Button, DemoBadge, Panel, Stat, StateView } from "@/components/ui/primitives";
import { ConfidenceHistogram } from "@/components/analytics/confidence-histogram";
import { FrameTimeline } from "@/components/analytics/frame-timeline";

export default function AnalyticsPage() {
  const { state, threshold, setThreshold } = useAnalysis();
  const { result, phase, job, error, file } = state;
  const summary = useMemo(() => (result ? summarizeFrames(result.frames, threshold) : null), [result, threshold]);
  const detections = useMemo(() => (result ? allDetections(result.frames) : []), [result]);
  const aboveThreshold = useMemo(() => filterByConfidence(detections, threshold), [detections, threshold]);

  if (!result) {
    const busy = phase === "submitting" || phase === "processing";
    return (
      <div className="space-y-4">
        <Panel>
          {phase === "failed" ? (
            <StateView role="alert" tone="danger" icon={<TriangleAlert className="size-5" aria-hidden />} title="Son analiz başarısız oldu" description={error?.message}
              action={<Link href="/workspace"><Button variant="primary">Çalışma alanına dön</Button></Link>} />
          ) : busy ? (
            <StateView role="status" tone="accent" icon={<BarChart3 className="size-5" aria-hidden />} title="Analiz sürüyor"
              description={`İşlem durumu: ${job?.status ?? "başlatılıyor"}. Sonuçlar tamamlandığında burada görünür.`} />
          ) : (
            <StateView icon={<BarChart3 className="size-5" aria-hidden />} title="Henüz analiz sonucu yok"
              description="Sayılar, güven dağılımı ve zaman çizelgesi, Detection Workspace'te bir analiz tamamlandığında burada görünür. Gerçek veri olmadan örnek değer gösterilmez."
              action={<Link href="/workspace"><Button variant="primary">Çalışma alanına git</Button></Link>} />
          )}
        </Panel>
        <HistoryPlaceholder />
      </div>
    );
  }

  const isVideo = result.media.kind === "video";
  const mock = result.provenance === "mock";

  return (
    <div className="space-y-4">
      {mock && (
        <div role="note" className="flex flex-wrap items-center gap-2 rounded-lg border border-warn/30 bg-warn-soft/50 px-4 py-2.5 text-[13px] text-warn">
          <DemoBadge /> Bu sayfadaki tüm değerler yapay demo verisinden hesaplanmıştır; gerçek model çıkarımı değildir.
        </div>
      )}

      <Panel title="Sonuç özeti" aside={<span className="truncate">{file?.name}</span>}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-5 md:grid-cols-5">
          <Stat label="Toplam tespit" value={summary?.totalDetections ?? "—"} tone="accent" hint={isVideo ? "Kare toplamı; benzersiz kişi sayısı değildir" : "Eşik üstü"} />
          <Stat label="Kare başına tepe" value={summary?.peakDetectionsPerFrame ?? "—"} hint="Tek karedeki en çok tespit" />
          <Stat label="Ortalama skor" value={summary?.meanConfidence == null ? "—" : formatConfidence(summary.meanConfidence)} hint="Eşik üstü tespitler" />
          <Stat label="Analiz edilen kare" value={summary?.framesAnalyzed ?? "—"} hint={summary ? `${summary.framesWithDetections} karede tespit var` : undefined} />
          <Stat label="Analiz süresi" value={formatDurationMs(result.timing.processingMs)} hint={result.timing.measured ? "Ölçülen" : "Simülasyon süresi"} tone={result.timing.measured ? undefined : "warn"} />
        </dl>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel title="Güven skoru dağılımı" aside={<span className="tnum">{detections.length} tespit (eşik öncesi)</span>}>
          <ConfidenceHistogram detections={detections} threshold={threshold} />
          <div className="mt-4 flex items-center gap-3 border-t border-line pt-3">
            <label htmlFor="an-threshold" className="shrink-0 text-xs text-muted">Güven eşiği</label>
            <input id="an-threshold" type="range" className="range min-w-0 flex-1" min={0} max={1} step={0.01} value={threshold}
              style={{ ["--fill" as string]: `${threshold * 100}%` }}
              onChange={(e) => setThreshold(Math.max(result.minConfidenceApplied, Number(e.target.value)))} />
            <output htmlFor="an-threshold" className="tnum w-10 text-right font-mono text-sm text-accent">{threshold.toFixed(2)}</output>
          </div>
          <p className="tnum mt-2 text-[11px] text-subtle">Eşik üstü: {aboveThreshold.length} / {detections.length}</p>
        </Panel>

        <Panel title="İşlem durumu">
          <dl className="space-y-2.5 text-[13px]">
            {[
              ["Durum", <Badge key="s" tone="ok">Tamamlandı</Badge>],
              ["İş kimliği", <span key="j" className="font-mono text-xs">{result.jobId}</span>],
              ["Kaynak", <span key="p">{mock ? "Mock (model yok)" : "Model"}</span>],
              ["Model", <span key="m">{result.model.name}{result.model.version ? ` · ${result.model.version}` : ""}</span>],
              ["Medya", <span key="d" className="tnum">{result.media.width}×{result.media.height} px{result.media.durationMs ? ` · ${formatTimestamp(result.media.durationMs)}` : ""}</span>],
              ["Sunucu skor tabanı", <span key="t" className="tnum">{result.minConfidenceApplied.toFixed(2)}</span>],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex items-center justify-between gap-3">
                <dt className="text-subtle">{k}</dt>
                <dd className="text-right text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <Panel title="Video kareleri / zaman çizelgesi">
        {isVideo ? (
          <FrameTimeline frames={result.frames} durationMs={result.media.durationMs ?? 0} threshold={threshold} />
        ) : (
          <p className="text-[13px] text-muted">Bu analiz tek bir görüntüdür; zaman çizelgesi yalnızca video sonuçlarında oluşur.</p>
        )}
      </Panel>

      <HistoryPlaceholder />
    </div>
  );
}

function HistoryPlaceholder() {
  return (
    <Panel title="Analiz geçmişi" aside={<Badge>Planlı</Badge>}>
      <div className="flex items-start gap-3 text-[13px] leading-relaxed text-muted">
        <History className="mt-0.5 size-4 shrink-0 text-subtle" aria-hidden />
        <p>
          Geçmiş analizler için kalıcı depolama henüz yoktur; yalnızca geçerli oturumdaki son analiz tutulur ve sayfa yenilenince kaybolur.
          Backend hazır olduğunda geçmiş, <code className="font-mono text-xs text-ink">GET /api/v1/jobs</code> listesiyle eklenecektir (docs/api-contract.md, “Gelecek”).
        </p>
      </div>
    </Panel>
  );
}
