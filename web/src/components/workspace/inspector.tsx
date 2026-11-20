"use client";

import Link from "next/link";
import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import {
  Check,
  CircleSlash,
  FileVideo2,
  Image as ImageIcon,
  LoaderCircle,
  PanelRightClose,
  PanelRightOpen,
  Play,
  Replace,
  RotateCcw,
  ScanSearch,
  Square,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { useAnalysis, type Phase } from "@/state/analysis-store";
import type { AnalysisResult, DemoScenario } from "@/lib/api/contract";
import { allDetections, bandOf, confidenceHistogram, summarizeFrames } from "@/lib/detections/utils";
import { formatBytes, formatConfidence, formatDurationMs, formatTimestamp } from "@/lib/format";
import {
  Badge,
  Button,
  Eyebrow,
  GlassCard,
  IconButton,
  InfoDisclosure,
  ProgressBar,
  Segmented,
  StatusDot,
  Switch,
  Tooltip,
  cx,
  type Tone,
} from "@/components/ui/primitives";
import { VIEW_MODE_OPTIONS, type ViewPrefs } from "./view-prefs";
import type { RankedDetection } from "./ranked";

export const PHASE_LABEL: Record<Phase, { text: string; tone: Tone }> = {
  empty: { text: "Dosya bekleniyor", tone: "neutral" },
  ready: { text: "Hazır", tone: "neutral" },
  submitting: { text: "Gönderiliyor", tone: "cyan" },
  processing: { text: "İşleniyor", tone: "cyan" },
  succeeded: { text: "Tamamlandı", tone: "cyan" },
  failed: { text: "Başarısız", tone: "danger" },
  canceled: { text: "İptal edildi", tone: "amber" },
};

interface InspectorProps {
  items: readonly RankedDetection[];
  /** Geçerli karede eşikten önceki tespit sayısı. */
  frameTotal: number;
  frameLabel: string;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  prefs: ViewPrefs;
  onPrefsChange: (p: ViewPrefs) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

/* ================================================================== */
/* Görev bölümü — her zaman görünür                                     */
/* ================================================================== */

function PrimaryActions({ phase }: { phase: Phase }) {
  const { start, cancel, clear } = useAnalysis();
  if (phase === "empty") {
    return (
      <Button variant="secondary" size="lg" disabled className="w-full border-dashed">
        Analizi başlat · önce dosya seçin
      </Button>
    );
  }
  if (phase === "submitting" || phase === "processing") {
    return (
      <Button variant="secondary" className="w-full" onClick={() => void cancel()}>
        <Square className="size-4" aria-hidden /> Analizi iptal et
      </Button>
    );
  }
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      {phase === "ready" ? (
        <Button variant="primary" size="lg" className="w-full sm:flex-1" onClick={() => void start()}>
          <Play className="size-4" aria-hidden /> Analizi başlat
        </Button>
      ) : phase === "succeeded" ? (
        <Button variant="secondary" className="w-full sm:flex-1" onClick={() => void start()}>
          <RotateCcw className="size-4" aria-hidden /> Yeniden analiz
        </Button>
      ) : (
        <Button variant="primary" className="w-full sm:flex-1" onClick={() => void start()}>
          <RotateCcw className="size-4" aria-hidden /> Yeniden dene
        </Button>
      )}
      <Button variant="secondary" className="w-full sm:flex-1" onClick={clear}>
        <Replace className="size-4" aria-hidden /> Dosyayı değiştir
      </Button>
    </div>
  );
}

function DemoScenarioControl({ disabled }: { disabled: boolean }) {
  const { service } = useAnalysis();
  const demo = service.demo;
  const [value, setValue] = useState<DemoScenario>(() => demo?.getScenario() ?? "success");
  if (!demo) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber/25 bg-amber-soft/60 px-3 py-2">
      <span className="text-[13px] font-medium text-amber">Demo senaryosu</span>
      <Segmented
        label="Demo senaryosu"
        value={value}
        onChange={(s) => {
          demo.setScenario(s);
          setValue(s);
        }}
        options={[
          { value: "success", label: "Başarılı", disabled },
          { value: "failure", label: "Hata", disabled },
        ]}
      />
    </div>
  );
}

function JobSection({ collapseButton }: { collapseButton: ReactNode }) {
  const { state, service } = useAnalysis();
  const { phase, file, probe, job, result, error } = state;
  const label = PHASE_LABEL[phase];
  const busy = phase === "submitting" || phase === "processing";

  return (
    <section aria-labelledby="job-heading" className="space-y-4 border-b border-line px-5 py-4">
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>
          <span id="job-heading">Analiz görevi</span>
        </Eyebrow>
        {collapseButton}
      </div>

      {file && probe ? (
        <>
          <div className="flex items-center gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-line-strong bg-surface-2/80 text-cyan">
              {probe.kind === "video" ? <FileVideo2 className="size-5" aria-hidden /> : <ImageIcon className="size-5" aria-hidden />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold text-ink" title={file.name}>
                {file.name}
              </p>
              <p className="tnum truncate font-mono text-[13px] text-subtle">
                {probe.kind === "video" ? "Video" : "Görüntü"} · {probe.width}×{probe.height} · {formatBytes(file.size)}
                {probe.durationMs ? ` · ${formatTimestamp(probe.durationMs)}` : ""}
              </p>
            </div>
            <Badge tone={label.tone} role="status" className="shrink-0">
              {busy ? <LoaderCircle className="size-3.5 animate-spin" aria-hidden /> : phase === "succeeded" ? <Check className="size-3.5" aria-hidden /> : <StatusDot tone={label.tone} />}
              {label.text}
            </Badge>
          </div>

          {busy && (
            <div className="space-y-1.5">
              <ProgressBar label="Analiz ilerlemesi" ratio={phase === "submitting" ? null : (job?.progress.ratio ?? null)} />
              <p className="tnum flex justify-between font-mono text-[13px] text-muted">
                <span>{job?.progress.totalFrames != null ? `${job.progress.processedFrames} / ${job.progress.totalFrames} kare` : "Hazırlanıyor"}</span>
                <span>{job?.progress.ratio != null ? `%${Math.round(job.progress.ratio * 100)}` : ""}</span>
              </p>
            </div>
          )}

          {phase === "failed" && error && (
            <p role="alert" className="flex items-start gap-2 rounded-xl border border-danger/40 bg-danger-soft px-3 py-2.5 text-[13.5px] text-danger">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                {error.message} <span className="font-mono text-[12.5px] opacity-80">({error.code})</span>
              </span>
            </p>
          )}

          {(job || result) && (
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13.5px]">
              <dt className="text-subtle">İş kimliği</dt>
              <dd className="truncate text-right font-mono text-[13px] text-ink">{job?.id ?? "—"}</dd>
              <dt className="text-subtle">İşlem süresi</dt>
              <dd className="tnum text-right font-mono text-[13px] text-ink">
                {result ? `${formatDurationMs(result.timing.processingMs)}${result.timing.measured ? "" : " · simülasyon"}` : "—"}
              </dd>
              <dt className="text-subtle">Model</dt>
              <dd className="truncate text-right text-ink">
                {result ? (result.provenance === "mock" ? "Yok · mock üretici" : `${result.model.name}${result.model.version ? ` · ${result.model.version}` : ""}`) : "—"}
              </dd>
            </dl>
          )}

          <PrimaryActions phase={phase} />
          {service.demo && <DemoScenarioControl disabled={busy} />}
        </>
      ) : (
        <>
          <ol className="space-y-3">
            {[
              ["Dosya yükleyin", "Termal görüntü veya video"],
              ["Analizi başlatın", null],
              ["Tespitleri inceleyin", null],
            ].map(([t, d], i) => (
              <li key={t} className="flex items-start gap-3 text-sm">
                <span
                  className={cx(
                    "grid size-7 shrink-0 place-items-center rounded-lg border font-mono text-[13px] font-semibold",
                    i === 0 ? "border-cyan/50 bg-cyan-soft text-cyan" : "border-line-strong text-subtle",
                  )}
                >
                  {i + 1}
                </span>
                <span className={i === 0 ? "text-ink" : "text-muted"}>
                  <span className={i === 0 ? "font-semibold" : undefined}>{t}</span>
                  {d && <span className="block text-[13px] text-subtle">{d}</span>}
                </span>
              </li>
            ))}
          </ol>
          <PrimaryActions phase="empty" />
        </>
      )}
    </section>
  );
}

/* ================================================================== */
/* Eşik bölümü — her zaman görünür                                      */
/* ================================================================== */

function ThresholdSection({ result, frameVisible, frameTotal, isVideo }: { result: AnalysisResult | null; frameVisible: number; frameTotal: number; isVideo: boolean }) {
  const { threshold, setThreshold } = useAnalysis();
  const detections = useMemo(() => (result ? allDetections(result.frames) : []), [result]);
  const bins = useMemo(() => confidenceHistogram(detections, 10), [detections]);
  const summary = useMemo(() => (result ? summarizeFrames(result.frames, threshold) : null), [result, threshold]);
  const max = Math.max(1, ...bins.map((b) => b.count));
  const floor = result?.minConfidenceApplied ?? 0;
  const disabled = !result;
  const set = (v: number) => setThreshold(Math.min(1, Math.max(floor, Math.round(v * 100) / 100)));

  return (
    <section aria-labelledby="thr-heading" className={cx("border-b border-line px-5 py-4", disabled && "opacity-70")}>
      <div className="flex items-center justify-between gap-2">
        <Eyebrow>
          <label id="thr-heading" htmlFor="threshold">
            Güven eşiği
          </label>
        </Eyebrow>
        <InfoDisclosure title="Güven eşiği nasıl çalışır?">
          <ul className="list-disc space-y-1.5 pl-4">
            <li>Eşik yalnızca <b className="text-ink">görüntüleme filtresidir</b>; model çıktısını veya analizi değiştirmez.</li>
            <li>Skor modelin güven puanıdır; <b className="text-ink">kalibre edilmiş olasılık değildir</b>.</li>
            <li>Sunucu tabanının ({floor.toFixed(2)}) altındaki tespitler yanıtta yoktur; eşik düşürülerek geri getirilemez.</li>
            <li>0.25 arayüz varsayılanıdır; doğrulanmış bir işletim eşiği değildir.</li>
          </ul>
        </InfoDisclosure>
      </div>

      <div className="mt-1 flex items-end justify-between gap-3">
        <output htmlFor="threshold" className={cx("tnum font-mono text-[28px] font-semibold leading-none", disabled ? "text-disabled" : "text-cyan")}>
          {threshold.toFixed(2)}
        </output>
        {result ? (
          <div className="text-right text-[13.5px] leading-snug text-muted">
            <p>
              <span className="tnum font-semibold text-ink">{frameVisible}</span> / {frameTotal} {isVideo ? "bu karede" : "tespit"} görünür
            </p>
            {isVideo && summary && (
              <p className="text-[12.5px] text-subtle">
                Tüm kareler: <span className="tnum text-muted">{summary.totalDetections}</span> / {detections.length} (kare toplamı)
              </p>
            )}
          </div>
        ) : (
          <p className="text-[13.5px] text-subtle">Analizden sonra etkin</p>
        )}
      </div>

      {/* Eşikle etkileşen mini histogram: sütuna tıklamak eşiği o aralığın başına taşır */}
      <div className="mt-3 flex h-12 items-end gap-[3px]" role="group" aria-label="Skor dağılımı; bir aralığa tıklayarak eşiği ayarlayın">
        {bins.map((b) => {
          const below = b.to <= threshold + 1e-9;
          const band = bandOf((b.from + b.to) / 2);
          return (
            <button
              key={b.from}
              type="button"
              disabled={disabled}
              onClick={() => set(b.from)}
              aria-label={`${b.from.toFixed(1)}–${b.to.toFixed(1)} aralığı: ${b.count} tespit. Eşiği ${b.from.toFixed(1)} yap.`}
              className="group/bin flex h-full flex-1 items-end rounded-sm disabled:cursor-default"
            >
              <span
                className={cx(
                  "w-full rounded-t-[2px] transition-[background-color,height,opacity] duration-200 ease-out",
                  b.count === 0 ? "h-[3px] bg-line-strong" : below ? "bg-line-strong group-enabled/bin:group-hover/bin:bg-muted/50" : band === "low" ? "bg-cyan/55 group-enabled/bin:group-hover/bin:bg-cyan/80" : "bg-cyan/85 group-enabled/bin:group-hover/bin:bg-cyan",
                )}
                style={b.count > 0 ? { height: `${Math.max(10, (b.count / max) * 100)}%` } : undefined}
              />
            </button>
          );
        })}
      </div>
      <input
        id="threshold"
        type="range"
        className="range mt-1 w-full"
        min={0}
        max={1}
        step={0.01}
        value={threshold}
        disabled={disabled}
        style={{ ["--fill" as string]: `${threshold * 100}%` }}
        onChange={(e) => set(Number(e.target.value))}
        aria-valuetext={`${threshold.toFixed(2)} ve üzeri skorlar gösterilir`}
      />
      <div className="tnum flex justify-between font-mono text-xs text-subtle">
        <span>0.0</span>
        <span>0.5</span>
        <span>1.0</span>
      </div>
      <p className="mt-2 text-[13px] leading-snug text-muted">
        Yalnızca <b className="font-semibold text-ink">görüntüleme filtresi</b>. Skor kalibre olasılık değildir.
      </p>
    </section>
  );
}

/* ================================================================== */
/* Sekmeler                                                             */
/* ================================================================== */

type TabKey = "detections" | "details" | "view";

function Tabs({ value, onChange, count }: { value: TabKey; onChange: (t: TabKey) => void; count: number | null }) {
  const tabs: Array<{ key: TabKey; label: string }> = [
    { key: "detections", label: "Tespitler" },
    { key: "details", label: "Görev detayı" },
    { key: "view", label: "Görünüm" },
  ];
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = (i + dir + tabs.length) % tabs.length;
    refs.current[next]?.focus();
    onChange(tabs[next]!.key);
  };
  return (
    <div role="tablist" aria-label="Inceleme paneli sekmeleri" className="flex gap-1 border-b border-line px-3">
      {tabs.map((t, i) => {
        const on = value === t.key;
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${t.key}`}
            aria-selected={on}
            aria-controls={`panel-${t.key}`}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => onKey(e, i)}
            className={cx(
              "relative -mb-px flex h-11 items-center gap-1.5 whitespace-nowrap rounded-t-lg px-3 text-sm font-medium transition-colors duration-200",
              on ? "text-ink" : "text-muted hover:bg-raised/50 hover:text-ink",
            )}
          >
            {t.label}
            {t.key === "detections" && count !== null && (
              <span className="tnum rounded-md bg-cyan-soft px-1.5 font-mono text-xs text-cyan">{count}</span>
            )}
            <span aria-hidden className={cx("absolute inset-x-2 bottom-0 h-0.5 rounded-full transition-colors duration-200", on ? "bg-cyan" : "bg-transparent")} />
          </button>
        );
      })}
    </div>
  );
}

function DetectionCards({
  items,
  selectedId,
  hoveredId,
  onSelect,
  onHover,
  frameLabel,
  hasResult,
}: Pick<InspectorProps, "items" | "selectedId" | "hoveredId" | "onSelect" | "onHover" | "frameLabel"> & { hasResult: boolean }) {
  if (!hasResult) {
    return (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center text-sm text-muted">
        <ScanSearch className="size-6 text-subtle" aria-hidden />
        Analiz tamamlandığında tespit kartları burada görünür.
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 px-6 py-10 text-center text-sm text-muted">
        <ScanSearch className="size-6 text-subtle" aria-hidden />
        Bu karede eşik üstü tespit yok.
        <span className="text-[13px] text-subtle">Eşiği düşürmeyi veya başka bir zamana gitmeyi deneyin.</span>
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2 p-3" aria-label={`Tespitler, ${frameLabel}`}>
      {items.map(({ detection: d, rank }) => {
        const selected = d.id === selectedId;
        const hovered = d.id === hoveredId && !selected;
        const toggle = () => onSelect(selected ? null : d.id);
        return (
          <li key={d.id}>
            <GlassCard
              selected={selected}
              role="button"
              tabIndex={0}
              aria-pressed={selected}
              aria-label={`Tespit #${rank}, ${d.className}, skor ${formatConfidence(d.confidence)}`}
              onClick={toggle}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggle();
                }
              }}
              onPointerEnter={() => onHover(d.id)}
              onPointerLeave={() => onHover(null)}
              onFocus={() => onHover(d.id)}
              onBlur={() => onHover(null)}
              className={cx("grid cursor-pointer grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 px-3 py-3", hovered && "border-cyan/40")}
            >
              <span
                className={cx(
                  "row-span-2 grid size-10 place-items-center rounded-lg border font-mono text-[13px] font-semibold transition-colors duration-200",
                  selected ? "border-violet/55 bg-violet-soft text-violet" : "border-cyan/35 bg-cyan-soft text-cyan",
                )}
              >
                #{rank}
              </span>
              <span className="truncate text-[15px] font-semibold capitalize text-ink">{d.className}</span>
              <span className={cx("tnum font-mono text-base font-semibold", selected ? "text-violet" : "text-ink")}>{formatConfidence(d.confidence)}</span>
              <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-line-strong" aria-hidden>
                <span
                  className={cx("block h-full rounded-full transition-[background-color] duration-200", selected ? "bg-violet" : bandOf(d.confidence) === "low" ? "bg-cyan/55" : "bg-cyan")}
                  style={{ width: `${d.confidence * 100}%` }}
                />
              </span>
              <span className="tnum col-span-3 flex flex-wrap justify-between gap-x-3 font-mono text-[12.5px] text-muted">
                <span>
                  x {Math.round(d.box.x)} · y {Math.round(d.box.y)} · {Math.round(d.box.width)}×{Math.round(d.box.height)} px
                </span>
                <span className="text-subtle">{frameLabel}</span>
              </span>
              <span className="col-span-3">
                <span className="inline-flex h-6 items-center rounded-md border border-dashed border-line-strong px-2 text-xs text-subtle">
                  Operatör doğrulaması · planlı
                </span>
              </span>
            </GlassCard>
          </li>
        );
      })}
    </ul>
  );
}

function DetailRow({ k, v, hint }: { k: string; v: ReactNode; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-[13.5px] text-subtle">
        {k}
        {hint && <span className="block text-xs text-subtle/90">{hint}</span>}
      </dt>
      <dd className="tnum text-right font-mono text-[13px] text-ink">{v}</dd>
    </div>
  );
}

function JobDetails({ result }: { result: AnalysisResult | null }) {
  const { threshold } = useAnalysis();
  const s = useMemo(() => (result ? summarizeFrames(result.frames, threshold) : null), [result, threshold]);
  if (!result || !s) {
    return <p className="px-5 py-8 text-center text-sm text-muted">Görev ayrıntıları analiz tamamlanınca görünür.</p>;
  }
  const mock = result.provenance === "mock";
  const isVideo = result.media.kind === "video";
  return (
    <div className="space-y-4 p-5">
      <dl className="divide-y divide-line">
        <DetailRow k="Kaynak" v={mock ? "Mock üretici (model yok)" : "Model çıktısı"} />
        <DetailRow k="Medya" v={`${result.media.width}×${result.media.height} px${result.media.durationMs ? ` · ${formatTimestamp(result.media.durationMs)}` : ""}`} />
        <DetailRow k="Sınıflar" v={result.model.classes.map((c) => c.name).join(", ") || "—"} />
        <DetailRow k="Sunucu skor tabanı" v={result.minConfidenceApplied.toFixed(2)} />
        {isVideo && <DetailRow k="Kare adımı" v={`her ${result.frameStride}. kare`} />}
        <DetailRow k="Analiz edilen kare" v={s.framesAnalyzed} />
        {isVideo && <DetailRow k="Tespit içeren kare" v={s.framesWithDetections} hint="eşik üstü" />}
        {isVideo && <DetailRow k="Kare başına tepe" v={s.peakDetectionsPerFrame} hint="tek karedeki en çok tespit" />}
        <DetailRow k={isVideo ? "Toplam tespit" : "Tespit"} v={s.totalDetections} hint={isVideo ? "kare toplamı; benzersiz kişi sayısı değildir" : "eşik üstü"} />
        <DetailRow k="Ortalama skor" v={s.meanConfidence === null ? "—" : formatConfidence(s.meanConfidence)} hint="eşik üstü tespitler" />
        <DetailRow k="İşlem süresi" v={`${formatDurationMs(result.timing.processingMs)}${result.timing.measured ? "" : " · simülasyon"}`} />
      </dl>
      <div className="rounded-xl border border-dashed border-line-strong p-4 text-[13.5px] leading-relaxed text-muted">
        <p className="mb-1 font-semibold text-ink">Model ayrıntıları · planlı</p>
        Backend model kaydını (çalıştırma kimliği, ağırlık özeti, değerlendirme kapsamı) bildirdiğinde burada gösterilecek. Eğitim ve değerlendirme metrikleri{" "}
        <Link href="/lab" className="font-medium text-cyan underline-offset-4 hover:underline">
          Model &amp; Dataset Lab
        </Link>{" "}
        modülüne aittir.
      </div>
    </div>
  );
}

function ViewControls({ prefs, onPrefsChange, result }: { prefs: ViewPrefs; onPrefsChange: (p: ViewPrefs) => void; result: AnalysisResult | null }) {
  const disabled = !result;
  return (
    <div className="space-y-5 p-5">
      <div className="space-y-2">
        <Eyebrow>Görünüm modu</Eyebrow>
        <Segmented
          label="Görünüm modu"
          value={prefs.mode}
          onChange={(mode) => onPrefsChange({ ...prefs, mode })}
          className="flex w-full"
          options={VIEW_MODE_OPTIONS.map((o) => ({ ...o, disabled }))}
        />
        {prefs.mode === "split" && result && (
          <Button variant="ghost" size="sm" onClick={() => onPrefsChange({ ...prefs, splitPct: 50 })}>
            Ayırıcıyı ortala
          </Button>
        )}
      </div>
      <div className="space-y-1">
        <Eyebrow>Katmanlar</Eyebrow>
        <Switch label="Tespit kutuları" checked={prefs.showBoxes} disabled={disabled} onChange={(showBoxes) => onPrefsChange({ ...prefs, showBoxes })} />
        <Switch label="Skor etiketleri" checked={prefs.showLabels} disabled={disabled || !prefs.showBoxes} onChange={(showLabels) => onPrefsChange({ ...prefs, showLabels })} />
        {(result?.model.classes ?? []).map((c) => (
          <Switch
            key={c.id}
            label={`Sınıf: ${c.name}`}
            checked={!prefs.hiddenClasses.has(c.id)}
            disabled={disabled || !prefs.showBoxes}
            onChange={(on) => {
              const next = new Set(prefs.hiddenClasses);
              if (on) next.delete(c.id);
              else next.add(c.id);
              onPrefsChange({ ...prefs, hiddenClasses: next });
            }}
          />
        ))}
      </div>
      <div className="space-y-2.5">
        <Eyebrow>Kutu gösterimi</Eyebrow>
        <ul className="space-y-2 text-[13.5px] text-muted">
          <li className="flex items-center gap-3"><span aria-hidden className="h-4 w-6 rounded-[2px] border-[1.5px] border-cyan" />Skor ≥ 0.50</li>
          <li className="flex items-center gap-3"><span aria-hidden className="h-4 w-6 rounded-[2px] border-[1.5px] border-dashed border-cyan" />Skor &lt; 0.50 (kesikli)</li>
          <li className="flex items-center gap-3"><span aria-hidden className="h-4 w-6 rounded-[2px] border-2 border-violet" />Seçili tespit</li>
        </ul>
        <p className="text-[13px] text-subtle">Bantlar yalnızca görsel ayrımdır; güvenilirlik sınıflandırması değildir.</p>
      </div>
    </div>
  );
}

/* ================================================================== */
/* Daraltılmış şerit                                                    */
/* ================================================================== */

function CollapsedStrip({ onExpand, frameVisible }: { onExpand: () => void; frameVisible: number }) {
  const { state, threshold, start, cancel, service } = useAnalysis();
  const { phase, result } = state;
  const label = PHASE_LABEL[phase];
  const busy = phase === "submitting" || phase === "processing";
  const StatusIcon = busy ? LoaderCircle : phase === "succeeded" ? Check : phase === "failed" ? TriangleAlert : phase === "canceled" ? CircleSlash : phase === "empty" ? Upload : Play;
  const ring = { neutral: "border-line-strong text-muted", cyan: "border-cyan/45 bg-cyan-soft text-cyan", violet: "", amber: "border-amber/45 bg-amber-soft text-amber", danger: "border-danger/45 bg-danger-soft text-danger" }[label.tone];

  return (
    <div className="flex h-full flex-col items-center gap-4 py-4">
      <IconButton label="İnceleme panelini aç" side="left" onClick={onExpand} aria-expanded={false} aria-controls="inspector-panel">
        <PanelRightOpen className="size-[18px]" />
      </IconButton>
      <Tooltip label={`Durum: ${label.text}`} side="left">
        <span tabIndex={0} role="status" aria-label={`Durum: ${label.text}`} className={cx("grid size-10 place-items-center rounded-xl border", ring)}>
          <StatusIcon className={cx("size-[18px]", busy && "animate-spin")} aria-hidden />
        </span>
      </Tooltip>
      {result && (
        <>
          <Tooltip label="Geçerli karede eşik üstü tespit" side="left">
            <span tabIndex={0} className="tnum flex flex-col items-center rounded-md font-mono text-base font-semibold text-ink" aria-label={`Bu karede ${frameVisible} tespit`}>
              {frameVisible}
              <span className="font-sans text-[10.5px] font-semibold tracking-wider text-subtle">KAREDE</span>
            </span>
          </Tooltip>
          <Tooltip label="Güven eşiği (görüntüleme filtresi)" side="left">
            <span tabIndex={0} className="tnum flex flex-col items-center rounded-md font-mono text-sm font-semibold text-cyan" aria-label={`Eşik ${threshold.toFixed(2)}`}>
              {threshold.toFixed(2)}
              <span className="font-sans text-[10.5px] font-semibold tracking-wider text-subtle">EŞİK</span>
            </span>
          </Tooltip>
        </>
      )}
      {phase === "ready" && (
        <Tooltip label="Analizi başlat" side="left">
          <button type="button" aria-label="Analizi başlat" onClick={() => void start()} className="grid size-11 place-items-center rounded-xl bg-cyan text-[#04121A] transition-[background-color,transform] duration-200 hover:bg-[#3fd6e4] active:scale-95">
            <Play className="size-5" />
          </button>
        </Tooltip>
      )}
      {busy && (
        <IconButton label="Analizi iptal et" side="left" onClick={() => void cancel()}>
          <Square className="size-4" />
        </IconButton>
      )}
      {(phase === "succeeded" || phase === "failed" || phase === "canceled") && (
        <IconButton label={phase === "succeeded" ? "Yeniden analiz" : "Yeniden dene"} side="left" onClick={() => void start()}>
          <RotateCcw className="size-[18px]" />
        </IconButton>
      )}
      {service.mode === "mock" && (
        <Tooltip label="DEMO / MOCK verisi" side="left">
          <span tabIndex={0} aria-label="DEMO / MOCK verisi" className="mt-auto rounded-md border border-amber/45 bg-amber-soft px-1.5 py-1 font-mono text-[10.5px] font-semibold text-amber">
            DEMO
          </span>
        </Tooltip>
      )}
    </div>
  );
}

/* ================================================================== */
/* Inspector                                                            */
/* ================================================================== */

export function Inspector(props: InspectorProps) {
  const { state } = useAnalysis();
  const { result, kind } = state;
  const [tab, setTab] = useState<TabKey>("detections");
  const panelId = useId();

  if (props.collapsed) {
    return (
      <aside id="inspector-panel" aria-label="İnceleme paneli (daraltılmış)" className="glass glass-edge h-full w-[72px] shrink-0 rounded-none border-y-0 border-r-0">
        <CollapsedStrip onExpand={props.onToggleCollapsed} frameVisible={props.items.length} />
      </aside>
    );
  }

  return (
    <aside
      id="inspector-panel"
      aria-label="İnceleme paneli"
      className="glass glass-edge flex flex-col max-lg:rounded-2xl lg:h-full lg:w-[372px] lg:shrink-0 lg:overflow-y-auto lg:rounded-none lg:border-y-0 lg:border-r-0"
    >
      <JobSection
        collapseButton={
          <span className="hidden lg:inline-flex">
            <IconButton label="İnceleme panelini daralt" side="left" onClick={props.onToggleCollapsed} aria-expanded aria-controls="inspector-panel">
              <PanelRightClose className="size-[18px]" />
            </IconButton>
          </span>
        }
      />
      <ThresholdSection result={result} frameVisible={props.items.length} frameTotal={props.frameTotal} isVideo={kind === "video"} />
      <Tabs value={tab} onChange={setTab} count={result ? props.items.length : null} />
      <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} data-panel={panelId} className="min-h-0 flex-1 lg:min-h-[180px] lg:overflow-y-auto">
        {tab === "detections" && (
          <DetectionCards
            items={props.items}
            selectedId={props.selectedId}
            hoveredId={props.hoveredId}
            onSelect={props.onSelect}
            onHover={props.onHover}
            frameLabel={props.frameLabel}
            hasResult={result !== null}
          />
        )}
        {tab === "details" && <JobDetails result={result} />}
        {tab === "view" && <ViewControls prefs={props.prefs} onPrefsChange={props.onPrefsChange} result={result} />}
        {/* Rapor dışa aktarma: altyapı yok; düğme pasif ve "Planlı" olarak işaretli */}
        <div className="flex items-center gap-2 border-t border-line px-4 py-3">
          <Button variant="secondary" disabled className="flex-1 border-dashed" title="Rapor altyapısı henüz yok">
            Rapor dışa aktar · PDF/CSV
          </Button>
          <Badge>Planlı</Badge>
        </div>
      </div>
    </aside>
  );
}
