"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAnalysis } from "@/state/analysis-store";
import { filterByConfidence, findFrameAt } from "@/lib/detections/utils";
import { formatTimestamp } from "@/lib/format";
import { Segmented, Switch } from "@/components/ui/primitives";
import { MediaStage } from "@/components/workspace/media-stage";
import { WorkspaceDock } from "@/components/workspace/workspace-dock";
import { Inspector } from "@/components/workspace/inspector";
import { DEFAULT_VIEW_PREFS, VIEW_MODE_OPTIONS, type ViewPrefs } from "@/components/workspace/view-prefs";
import { rankDetections } from "@/components/workspace/ranked";
import { useMediaClock } from "@/components/workspace/use-media-clock";
import { useIsDesktop } from "@/components/workspace/use-is-desktop";

const COLLAPSE_KEY = "therma.inspectorCollapsed";

/**
 * Detection Workspace — bölünmüş çalışma alanı.
 * Masaüstü: [görüntü sütunu: araç çubuğu · sahne · sabit oynatıcı] | [inspector 372 px veya 72 px].
 * Sayfa yüksekliği görünüm alanına sabitlenir; sahne küçülür, oynatıcı ve zaman çizelgesi aşağı kaymaz.
 * Mobil: tek sütun, doğal akış.
 */
export default function WorkspacePage() {
  const { state, threshold } = useAnalysis();
  const { result, kind, phase, file, probe } = state;
  const [prefs, setPrefs] = useState<ViewPrefs>(DEFAULT_VIEW_PREFS);
  const [selectedRaw, setSelected] = useState<string | null>(null);
  const [hoveredId, setHovered] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const isDesktop = useIsDesktop();
  const isVideo = kind === "video";
  const clock = useMediaClock(videoRef, isVideo && phase !== "empty");

  // Daraltma tercihi yalnızca bu tarayıcıda hatırlanır; okunamazsa varsayılan açık.
  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- tek seferlik, istemciye özgü tercih okuması
      if (window.localStorage.getItem(COLLAPSE_KEY) === "1") setCollapsed(true);
    } catch {
      /* depolama kullanılamıyor */
    }
  }, []);
  const toggleCollapsed = () =>
    setCollapsed((c) => {
      try {
        window.localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* yok say */
      }
      return !c;
    });

  const currentFrame = useMemo(() => {
    if (!result) return null;
    if (result.media.kind === "image") return result.frames[0] ?? null;
    // Analiz edilmeyen aralıkta eski kutular gösterilmesin: tolerans = 2 örnekleme aralığı.
    const step = result.frames.length > 1 ? result.frames[1]!.timestampMs - result.frames[0]!.timestampMs : 1000;
    return findFrameAt(result.frames, clock.timeMs, Math.max(500, step * 2));
  }, [result, clock.timeMs]);

  const classVisible = useMemo(
    () => (currentFrame ? currentFrame.detections.filter((d) => !prefs.hiddenClasses.has(d.classId)) : []),
    [currentFrame, prefs.hiddenClasses],
  );
  const items = useMemo(() => rankDetections(filterByConfidence(classVisible, threshold)), [classVisible, threshold]);
  const selectedId = items.some((r) => r.detection.id === selectedRaw) ? selectedRaw : null;
  const frameLabel = !result ? "—" : isVideo ? `t ${formatTimestamp(currentFrame?.timestampMs ?? clock.timeMs)}` : "tek kare";
  const succeeded = phase === "succeeded" && result !== null;

  return (
    <div className="flex flex-col gap-4 p-3 sm:p-4 lg:h-[calc(100dvh-56px)] lg:flex-row lg:gap-0 lg:p-0">
      <section aria-label="Görüntü sütunu" className="flex min-w-0 flex-1 flex-col gap-3 lg:min-h-0 lg:p-4 lg:pr-4">
        {/* Araç çubuğu */}
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-base font-semibold text-ink">{file ? file.name : "Görüntü izleme alanı"}</h2>
            {probe && (
              <p className="tnum truncate font-mono text-[13px] text-subtle">
                {probe.width}×{probe.height} · {probe.kind === "video" ? "VİDEO" : "GÖRÜNTÜ"}
                {probe.durationMs ? ` · ${formatTimestamp(probe.durationMs)}` : ""}
              </p>
            )}
          </div>
          {file && (
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
              <Segmented
                label="Görünüm modu"
                value={prefs.mode}
                onChange={(mode) => setPrefs({ ...prefs, mode })}
                className="flex w-full sm:w-auto"
                options={VIEW_MODE_OPTIONS.map((o) => ({ ...o, disabled: !succeeded }))}
              />
              <div className="hidden items-center xl:flex">
                <Switch compact label="Kutular" checked={prefs.showBoxes} disabled={!succeeded} onChange={(showBoxes) => setPrefs({ ...prefs, showBoxes })} />
                <Switch compact label="Skorlar" checked={prefs.showLabels} disabled={!succeeded || !prefs.showBoxes} onChange={(showLabels) => setPrefs({ ...prefs, showLabels })} />
              </div>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1">
          <MediaStage
            videoRef={videoRef}
            prefs={prefs}
            onPrefsChange={setPrefs}
            items={items}
            frameTotal={classVisible.length}
            selectedId={selectedId}
            hoveredId={hoveredId}
            onSelect={setSelected}
            onHover={setHovered}
            timeMs={clock.timeMs}
          />
        </div>

        <WorkspaceDock kind={kind} videoRef={videoRef} clock={clock} result={result} threshold={threshold} />
      </section>

      <Inspector
        items={items}
        frameTotal={classVisible.length}
        frameLabel={frameLabel}
        selectedId={selectedId}
        hoveredId={hoveredId}
        onSelect={setSelected}
        onHover={setHovered}
        prefs={prefs}
        onPrefsChange={setPrefs}
        collapsed={collapsed && isDesktop}
        onToggleCollapsed={toggleCollapsed}
      />
    </div>
  );
}
