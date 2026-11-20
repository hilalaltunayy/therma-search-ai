"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Info, X } from "lucide-react";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/**
 * Cam kartlarda imleci izleyen yansıma için CSS değişkenlerini (--mx, --my) günceller.
 * Yalnızca fare ile çalışır; dokunmatikte etkisizdir (hover'a bağımlı etkileşim yok).
 */
export function trackSpotlight(e: PointerEvent<HTMLElement>) {
  if (e.pointerType !== "mouse") return;
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty("--mx", `${e.clientX - r.left}px`);
  el.style.setProperty("--my", `${e.clientY - r.top}px`);
}

/* ---------------------------- Glass panel ---------------------------- */

interface GlassPanelProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  aside?: ReactNode;
  padded?: boolean;
  /** Üst kenarda ince ışık çizgisi. */
  edge?: boolean;
}

/** Statik cam yüzey (inspector bölümleri, analitik panelleri). Etkileşimli kart için GlassCard kullanın. */
export function GlassPanel({ title, aside, padded = true, edge = true, className, children, ...rest }: GlassPanelProps) {
  return (
    <section className={cx("glass rounded-2xl", edge && "glass-edge", className)} {...rest}>
      {(title || aside) && (
        <header className="flex min-h-12 items-center justify-between gap-3 border-b border-line px-5 py-3">
          {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
          {aside && <div className="flex items-center gap-2 text-[13px] text-muted">{aside}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : undefined}>{children}</div>
    </section>
  );
}

/** Etkileşimli cam kart: hover (cyan yansıma + 1px yükselme), seçim (violet), focus (cyan halka). */
export function GlassCard({
  selected,
  className,
  children,
  ...rest
}: { selected?: boolean } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div data-selected={selected ? "true" : undefined} onPointerMove={trackSpotlight} className={cx("glass-card rounded-xl", className)} {...rest}>
      {children}
    </div>
  );
}

/* ---------------------------- Badge ---------------------------- */

export type Tone = "neutral" | "cyan" | "violet" | "amber" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "border-line-strong bg-surface-2/70 text-muted",
  cyan: "border-cyan/40 bg-cyan-soft text-cyan",
  violet: "border-violet/45 bg-violet-soft text-violet",
  amber: "border-amber/45 bg-amber-soft text-amber",
  danger: "border-danger/45 bg-danger-soft text-danger",
};

export function Badge({ tone = "neutral", className, children, ...rest }: { tone?: Tone } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cx("inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-lg border px-2.5 text-[12.5px] font-medium", toneClasses[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}

export function StatusDot({ tone = "neutral", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const color = { neutral: "bg-disabled", cyan: "bg-cyan", violet: "bg-violet", amber: "bg-amber", danger: "bg-danger" }[tone];
  return <span aria-hidden className={cx("inline-block size-2 shrink-0 rounded-full", color, pulse && "animate-pulse-dot")} />;
}

/** DEMO / MOCK etiketi — sahte sonuç gösteren her alanda kullanılır. */
export function DemoBadge({ className, label = "DEMO / MOCK" }: { className?: string; label?: string }) {
  return (
    <Badge tone="amber" className={cx("font-semibold tracking-wide", className)} title="Bu değerler gerçek model çıktısı değildir.">
      {label}
    </Badge>
  );
}

/* ---------------------------- Buttons ---------------------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const buttonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cyan text-[#04121A] font-semibold shadow-[0_6px_18px_-8px_rgb(34_201_217/0.6)] hover:bg-[#3fd6e4] hover:shadow-[0_8px_24px_-8px_rgb(34_201_217/0.75)] disabled:bg-surface disabled:text-disabled disabled:shadow-none",
  secondary:
    "border border-line-strong bg-surface-2/70 text-ink hover:border-cyan/45 hover:bg-raised hover:text-ink disabled:border-line disabled:text-disabled disabled:hover:bg-surface-2/70",
  ghost: "text-muted hover:bg-raised/70 hover:text-ink disabled:text-disabled disabled:hover:bg-transparent",
  danger: "border border-danger/45 bg-danger-soft text-danger hover:bg-danger/20",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...rest
}: { variant?: ButtonVariant; size?: "sm" | "md" | "lg" } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-out active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100",
        size === "sm" ? "h-9 px-3" : size === "lg" ? "h-12 px-5 text-[15px]" : "h-11 px-4",
        buttonClasses[variant],
        className,
      )}
      {...rest}
    />
  );
}

/** Kare ikon düğmesi. `label` hem aria-label hem tooltip olur. */
export function IconButton({
  label,
  side = "bottom",
  active,
  className,
  children,
  ...rest
}: { label: string; side?: TooltipSide; active?: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <Tooltip label={label} side={side}>
      <button
        type="button"
        aria-label={label}
        className={cx(
          "grid size-10 place-items-center rounded-xl border transition-[background-color,border-color,color,transform] duration-200 ease-out active:scale-95 disabled:cursor-not-allowed disabled:opacity-50",
          active ? "border-cyan/45 bg-cyan-soft text-cyan" : "border-line-strong bg-surface-2/70 text-muted hover:border-cyan/40 hover:bg-raised hover:text-ink",
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    </Tooltip>
  );
}

/* ---------------------------- Tooltip ---------------------------- */

type TooltipSide = "top" | "bottom" | "bottom-end" | "left" | "right";

const sideClasses: Record<TooltipSide, string> = {
  top: "bottom-full left-1/2 mb-2 -translate-x-1/2",
  bottom: "top-full left-1/2 mt-2 -translate-x-1/2",
  "bottom-end": "top-full right-0 mt-2",
  left: "right-full top-1/2 mr-2 -translate-y-1/2",
  right: "left-full top-1/2 ml-3 -translate-y-1/2",
};

/**
 * Görsel tooltip (hover ve klavye odağında). Erişilebilir ad tetikleyicinin aria-label'ından gelir;
 * tooltip ekran okuyucuya tekrar okunmasın diye aria-hidden'dır.
 */
export function Tooltip({ label, side = "top", children }: { label: string; side?: TooltipSide; children: ReactNode }) {
  return (
    <span className="group/tt relative inline-flex">
      {children}
      <span
        aria-hidden
        className={cx(
          "pointer-events-none absolute z-50 whitespace-nowrap rounded-lg border border-line-strong bg-[#0c1422]/95 px-2.5 py-1.5 text-[13px] text-ink opacity-0 shadow-xl backdrop-blur transition-opacity duration-150 ease-out group-hover/tt:opacity-100 group-has-[:focus-visible]/tt:opacity-100",
          sideClasses[side],
        )}
      >
        {label}
      </span>
    </span>
  );
}

/* ---------------------------- Info disclosure ---------------------------- */

/** "Bu nedir?" açılır bilgi paneli. Dokunmatikte de çalışır (tıklama), Esc ve dış tıklama kapatır. */
export function InfoDisclosure({ label = "Bu nedir?", title, children }: { label?: string; title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-10 items-center gap-1.5 rounded-lg px-2.5 text-[13px] text-subtle transition-colors duration-200 hover:bg-raised/70 hover:text-ink"
      >
        <Info className="size-4" aria-hidden /> {label}
      </button>
      {open && (
        <div id={id} role="dialog" aria-label={title} className="glass glass-edge animate-rise absolute right-0 top-full z-40 mt-2 w-80 max-w-[85vw] rounded-xl p-4 text-[13.5px] leading-relaxed text-muted">
          <div className="mb-2 flex items-start justify-between gap-3">
            <p className="font-semibold text-ink">{title}</p>
            <button type="button" aria-label="Bilgi panelini kapat" onClick={() => setOpen(false)} className="-mr-1 -mt-1 grid size-7 place-items-center rounded-md text-subtle hover:bg-raised hover:text-ink">
              <X className="size-4" />
            </button>
          </div>
          {children}
        </div>
      )}
    </div>
  );
}

/* ---------------------------- Switch ---------------------------- */

export function Switch({
  checked,
  onChange,
  label,
  disabled,
  compact,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "group/sw inline-flex items-center justify-between gap-3 rounded-lg text-sm transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50",
        compact ? "h-9 px-1.5 text-muted hover:text-ink" : "h-10 w-full px-1 text-ink",
      )}
    >
      <span className={compact ? "order-2" : undefined}>{label}</span>
      <span
        aria-hidden
        className={cx(
          "relative h-[22px] w-10 shrink-0 rounded-full border transition-colors duration-200",
          checked ? "border-cyan/60 bg-cyan-soft group-hover/sw:border-cyan" : "border-line-strong bg-surface-2 group-hover/sw:border-muted/60",
        )}
      >
        <span
          className={cx(
            "absolute top-[3px] size-3.5 rounded-full transition-[left,background-color] duration-200 ease-out",
            checked ? "left-[21px] bg-cyan" : "left-[3px] bg-subtle",
          )}
        />
      </span>
    </button>
  );
}

/* ---------------------------- Segmented control ---------------------------- */

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string; disabled?: boolean }>;
  label: string;
  className?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cx("inline-flex rounded-xl border border-line-strong bg-surface-2/80 p-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={cx(
            "h-9 flex-1 whitespace-nowrap rounded-lg px-3.5 text-[13.5px] font-medium transition-[background-color,color,box-shadow] duration-200 ease-out disabled:cursor-not-allowed disabled:text-disabled",
            value === o.value
              ? "bg-raised text-ink shadow-[inset_0_0_0_1px_rgb(34_201_217/0.45)]"
              : "text-muted enabled:hover:bg-raised/60 enabled:hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------- Progress ---------------------------- */

export function ProgressBar({ ratio, label }: { ratio: number | null; label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={ratio === null ? undefined : Math.round(ratio * 100)}
      className="relative h-1.5 overflow-hidden rounded-full bg-line-strong"
    >
      {ratio === null ? (
        <div className="absolute inset-y-0 w-1/3 rounded-full bg-cyan [animation:indeterminate_1.4s_ease-in-out_infinite]" />
      ) : (
        <div className="h-full rounded-full bg-cyan transition-[width] duration-300 ease-out" style={{ width: `${Math.round(ratio * 100)}%` }} />
      )}
    </div>
  );
}

/* ---------------------------- State view ---------------------------- */

export function StateView({
  icon,
  title,
  description,
  action,
  tone = "neutral",
  role,
}: {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: Tone;
  role?: "alert" | "status";
}) {
  const ring = {
    neutral: "text-muted border-line-strong",
    cyan: "text-cyan border-cyan/35",
    violet: "text-violet border-violet/40",
    amber: "text-amber border-amber/40",
    danger: "text-danger border-danger/40",
  }[tone];
  return (
    <div role={role} className="animate-rise flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <div className={cx("grid size-14 place-items-center rounded-2xl border bg-surface-2/80", ring)}>{icon}</div>
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {description && <div className="max-w-md text-sm leading-relaxed text-muted">{description}</div>}
      {action && <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

/* ---------------------------- Section label ---------------------------- */

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("text-xs font-semibold uppercase tracking-[0.1em] text-subtle", className)}>{children}</p>;
}
