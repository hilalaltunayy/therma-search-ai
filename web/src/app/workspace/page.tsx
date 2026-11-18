"use client";

import { useMemo, useRef, useState } from "react";
import { ScanSearch } from "lucide-react";
import { useAnalysis } from "@/state/analysis-store";
import { filterByConfidence, findFrameAt, summarizeFrames } from "@/lib/detections/utils";
import { Panel, DemoBadge } from "@/components/ui/primitives";
import { MediaStage } from "@/components/workspace/media-stage";
import { PlayerControls } from "@/components/workspace/player-controls";
import { ControlsPanel } from "@/components/workspace/controls-panel";
import { JobPanel } from "@/components/workspace/job-panel";
import { DetectionList } from "@/components/workspace/detection-list";
import { MetricsStrip } from "@/components/workspace/metrics-strip";
import { FrameTimeline } from "@/components/analytics/frame-timeline";
import { DEFAULT_VIEW_PREFS, type ViewPrefs } from "@/components/workspace/view-prefs";
import { useMediaClock } from "@/components/workspace/use-media-clock";

export default function WorkspacePage() {
  const { state, threshold, setThreshold } = useAnalysis();
  const { result, kind, phase, file } = state;
  const [prefs, setPrefs] = useState<ViewPrefs>(DEFAULT_VIEW_PREFS);
  const [selectedRaw, setSelected] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const isVideo = kind === "video";
  const clock = useMediaClock(videoRef, isVideo && phase !== "empty");

  const currentFrame = useMemo(() => {
    if (!result) return null;
    if (result.media.kind === "image") return result.frames[0] ?? null;
    // Analiz edilmeyen aralıkta (stride) eski kutular gösterilmesin: tolerans = 2 örnekleme aralığı.
    const t = result.frames.length > 1 ? result.frames[1]!.timestampMs - result.frames[0]!.timestampMs : 1000;
    return findFrameAt(result.frames, clock.timeMs, Math.max(500, t * 2));
  }, [result, clock.timeMs]);

  const visible = useMemo(
    () => (currentFrame ? filterByConfidence(currentFrame.detections, threshold).filter((d) => !prefs.hiddenClasses.has(d.classId)) : []),
    [currentFrame, threshold, prefs.hiddenClasses],
  );
  const selectedId = visible.some((d) => d.id === selectedRaw) ? selectedRaw : null;
  const summary = useMemo(() => (result ? summarizeFrames(result.frames, threshold) : null), [result, threshold]);

  const mock = result?.provenance === "mock";
  const contextLabel = !result ? "—" : isVideo ? `t = ${(clock.timeMs / 1000).toFixed(1)} s` : "Tek kare";

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="min-w-0 space-y-4">
        <Panel
          title={file ? file.name : "Görüntü izleme alanı"}
          aside={mock ? <DemoBadge /> : undefined}
          padded={false}
          aria-label="Detection Workspace görüntüleme alanı"
        >
          <MediaStage videoRef={videoRef} prefs={prefs} onPrefsChange={setPrefs} visibleDetections={visible} selectedId={selectedId} />
          {isVideo && phase !== "empty" && <PlayerControls videoRef={videoRef} clock={clock} />}
          {isVideo && result && (
            <div className="border-t border-line px-4 py-3">
              <p className="mb-2 text-[11px] uppercase tracking-[0.08em] text-subtle">Tespit zaman çizelgesi</p>
              <FrameTimeline
                frames={result.frames}
                durationMs={result.media.durationMs ?? clock.durationMs}
                threshold={threshold}
                playheadMs={clock.timeMs}
                onSeek={(ms) => {
                  if (videoRef.current) videoRef.current.currentTime = ms / 1000;
                }}
              />
            </div>
          )}
        </Panel>

        <MetricsStrip result={result} summary={summary} currentFrameCount={result ? visible.length : null} />
      </div>

      <div className="space-y-4">
        <JobPanel />
        <ControlsPanel
          disabled={phase !== "succeeded"}
          prefs={prefs}
          onPrefsChange={setPrefs}
          threshold={threshold}
          onThresholdChange={setThreshold}
          minThreshold={result?.minConfidenceApplied ?? 0}
          classes={result?.model.classes ?? []}
        />
        {result ? (
          <DetectionList detections={visible} selectedId={selectedId} onSelect={setSelected} contextLabel={contextLabel} mock={mock} />
        ) : (
          <Panel title="Tespitler">
            <div className="flex flex-col items-center gap-2 py-4 text-center text-[13px] text-muted">
              <ScanSearch className="size-5 text-subtle" aria-hidden />
              Analiz tamamlandığında tespit listesi burada görünür.
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
