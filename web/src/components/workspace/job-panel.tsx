"use client";

import { useState } from "react";
import type { DemoScenario } from "@/lib/api/contract";
import { FileVideo2, ImageIcon, Play, RotateCcw, Replace } from "lucide-react";
import { useAnalysis, type Phase } from "@/state/analysis-store";
import { formatBytes, formatDurationMs, formatTimestamp } from "@/lib/format";
import { Badge, Button, DemoBadge, Panel, Segmented, StatusDot, type Tone } from "@/components/ui/primitives";

const phaseLabel: Record<Phase, { text: string; tone: Tone }> = {
  empty: { text: "Dosya bekleniyor", tone: "neutral" },
  ready: { text: "Analize hazır", tone: "accent" },
  submitting: { text: "İş oluşturuluyor", tone: "accent" },
  processing: { text: "İşleniyor", tone: "accent" },
  succeeded: { text: "Tamamlandı", tone: "ok" },
  failed: { text: "Başarısız", tone: "danger" },
  canceled: { text: "İptal edildi", tone: "warn" },
};

export function JobPanel() {
  const { state, service, start, clear } = useAnalysis();
  const { phase, file, probe, result, job } = state;
  const label = phaseLabel[phase];
  const busy = phase === "submitting" || phase === "processing";
  const mock = service.mode === "mock";

  return (
    <Panel
      title="Analiz işi"
      aside={
        <Badge tone={label.tone}>
          <StatusDot tone={label.tone} pulse={busy} />
          {label.text}
        </Badge>
      }
    >
      {file && probe ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg border border-line-strong bg-raised text-accent">
              {probe.kind === "video" ? <FileVideo2 className="size-5" aria-hidden /> : <ImageIcon className="size-5" aria-hidden />}
            </div>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-ink" title={file.name}>{file.name}</p>
              <p className="tnum mt-0.5 text-[11px] text-subtle">
                {probe.width}×{probe.height} px · {formatBytes(file.size)}
                {probe.durationMs ? ` · ${formatTimestamp(probe.durationMs)}` : ""}
              </p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
            <dt className="text-subtle">Tür</dt>
            <dd className="text-right text-ink">{probe.kind === "video" ? "Video" : "Görüntü"}</dd>
            <dt className="text-subtle">İş kimliği</dt>
            <dd className="truncate text-right font-mono text-ink">{job?.id ?? "—"}</dd>
            <dt className="text-subtle">İşlem süresi</dt>
            <dd className="tnum text-right text-ink">
              {result ? `${formatDurationMs(result.timing.processingMs)}${result.timing.measured ? "" : " (simülasyon)"}` : "—"}
            </dd>
            <dt className="text-subtle">Model</dt>
            <dd className="text-right text-ink">{result ? result.model.name : mock ? "Yok (demo)" : "—"}</dd>
          </dl>

          {result?.provenance === "mock" && (
            <div className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn-soft/60 p-2.5 text-[11px] leading-snug text-warn">
              <DemoBadge />
              <span>Kutular ve skorlar yapay üretilmiştir; görüntü içeriğiyle ilgisi yoktur.</span>
            </div>
          )}

          <div className="flex flex-col gap-2">
            {(phase === "ready" || phase === "failed" || phase === "canceled") && (
              <Button variant="primary" onClick={() => void start()}>
                {phase === "ready" ? <Play className="size-4" aria-hidden /> : <RotateCcw className="size-4" aria-hidden />}
                {phase === "ready" ? "Analizi başlat" : "Yeniden dene"}
              </Button>
            )}
            {phase === "succeeded" && (
              <Button variant="secondary" onClick={() => void start()}>
                <RotateCcw className="size-4" aria-hidden /> Yeniden analiz et
              </Button>
            )}
            <Button variant="ghost" disabled={busy} onClick={clear}>
              <Replace className="size-4" aria-hidden /> Dosyayı değiştir
            </Button>
          </div>

          {service.demo && (
            <div className="border-t border-line pt-3">
              <p className="mb-2 text-[11px] uppercase tracking-[0.08em] text-subtle">Demo senaryosu</p>
              <DemoScenarioSwitch disabled={busy} />
            </div>
          )}
        </div>
      ) : (
        <p className="text-[13px] leading-relaxed text-muted">
          Henüz dosya seçilmedi. Bir termal görüntü veya video yüklediğinizde iş durumu, süre ve model bilgisi burada görünür.
        </p>
      )}
    </Panel>
  );
}

function DemoScenarioSwitch({ disabled }: { disabled: boolean }) {
  const { service } = useAnalysis();
  const demo = service.demo!;
  // Senaryo servis içinde tutulur; yerel durum yalnızca yeniden çizim içindir.
  return <ScenarioControl disabled={disabled} get={demo.getScenario} set={demo.setScenario} />;
}


function ScenarioControl({ get, set, disabled }: { get: () => DemoScenario; set: (s: DemoScenario) => void; disabled: boolean }) {
  const [value, setValue] = useState<DemoScenario>(get());
  return (
    <Segmented
      label="Demo senaryosu"
      value={value}
      onChange={(s) => {
        set(s);
        setValue(s);
      }}
      options={[
        { value: "success", label: "Başarılı", disabled },
        { value: "failure", label: "Hata simülasyonu", disabled },
      ]}
    />
  );
}
