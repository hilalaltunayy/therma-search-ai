import type { AnalysisResult } from "@/lib/api/contract";
import type { DetectionSummary } from "@/lib/detections/utils";
import { formatConfidence, formatDurationMs } from "@/lib/format";
import { DemoBadge, Panel, Stat } from "@/components/ui/primitives";

interface Props {
  result: AnalysisResult | null;
  summary: DetectionSummary | null;
  currentFrameCount: number | null;
}

/** Gerçek sonuç yoksa "—" gösterilir; sıfır ile "ölçülmedi" ayrılır. */
export function MetricsStrip({ result, summary, currentFrameCount }: Props) {
  const isVideo = result?.media.kind === "video";
  const dash = "—";
  return (
    <Panel title="Özet" aside={result?.provenance === "mock" ? <DemoBadge /> : undefined}>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        <Stat label={isVideo ? "Bu karede" : "Tespit"} value={currentFrameCount ?? dash} tone="accent" hint="Eşik üstü" />
        <Stat
          label={isVideo ? "Kare başına tepe" : "Ortalama skor"}
          value={summary ? (isVideo ? summary.peakDetectionsPerFrame : summary.meanConfidence === null ? dash : formatConfidence(summary.meanConfidence)) : dash}
          hint={isVideo ? "Tek karedeki en çok tespit" : "Eşik üstü tespitler"}
        />
        <Stat
          label={isVideo ? "Toplam tespit" : "Analiz edilen kare"}
          value={summary ? (isVideo ? summary.totalDetections : summary.framesAnalyzed) : dash}
          hint={isVideo ? "Kare toplamı; benzersiz kişi sayısı değildir" : undefined}
        />
        <Stat
          label="Analiz süresi"
          value={result ? formatDurationMs(result.timing.processingMs) : dash}
          hint={result ? (result.timing.measured ? "Ölçülen" : "Simülasyon süresi") : undefined}
          tone={result && !result.timing.measured ? "warn" : undefined}
        />
      </dl>
    </Panel>
  );
}
