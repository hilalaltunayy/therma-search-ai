import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* ---------------------------- Panel ---------------------------- */

interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  /** Başlığın sağındaki eylem/etiket alanı. */
  aside?: ReactNode;
  padded?: boolean;
}

/** Tüm yüzeylerin temel birimi: ince çerçeve, kademeli yüzey rengi, tutarlı başlık satırı. */
export function Panel({ title, aside, padded = true, className, children, ...rest }: PanelProps) {
  return (
    <section
      className={cx("rounded-[var(--radius-panel)] border border-line bg-surface shadow-[var(--shadow-panel)]", className)}
      {...rest}
    >
      {(title || aside) && (
        <header className="flex min-h-11 items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          {title && <h2 className="text-[13px] font-semibold tracking-wide text-ink">{title}</h2>}
          {aside && <div className="flex items-center gap-2 text-xs text-muted">{aside}</div>}
        </header>
      )}
      <div className={padded ? "p-4" : undefined}>{children}</div>
    </section>
  );
}

/* ---------------------------- Badge ---------------------------- */

export type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

const toneClasses: Record<Tone, string> = {
  neutral: "border-line-strong bg-raised text-muted",
  accent: "border-accent/30 bg-accent-soft/60 text-accent",
  ok: "border-ok/30 bg-ok-soft text-ok",
  warn: "border-warn/40 bg-warn-soft text-warn",
  danger: "border-danger/40 bg-danger-soft text-danger",
};

export function Badge({ tone = "neutral", className, children, ...rest }: { tone?: Tone } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium leading-5",
        toneClasses[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

export function StatusDot({ tone = "neutral", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const color = { neutral: "bg-subtle", accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", danger: "bg-danger" }[tone];
  return <span aria-hidden className={cx("inline-block size-1.5 rounded-full", color, pulse && "animate-pulse-dot")} />;
}

/* ---------------------------- Button ---------------------------- */

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const buttonClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-base font-semibold hover:bg-accent-strong disabled:bg-line-strong disabled:text-subtle",
  secondary: "border border-line-strong bg-raised text-ink hover:border-accent/50 hover:bg-overlay disabled:text-subtle",
  ghost: "text-muted hover:bg-raised hover:text-ink disabled:text-subtle",
  danger: "border border-danger/40 bg-danger-soft text-danger hover:bg-danger/20",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...rest
}: { variant?: ButtonVariant; size?: "sm" | "md" } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-[13px] transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "h-8 px-3" : "h-10 px-4",
        buttonClasses[variant],
        className,
      )}
      {...rest}
    />
  );
}

/* ---------------------------- Switch ---------------------------- */

export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label className={cx("flex items-center justify-between gap-3 text-[13px]", disabled ? "opacity-50" : "cursor-pointer")}>
      <span className="text-ink">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative h-5 w-9 shrink-0 rounded-full border transition-colors",
          checked ? "border-accent/60 bg-accent-soft" : "border-line-strong bg-raised",
        )}
      >
        <span
          className={cx(
            "absolute top-0.5 size-3.5 rounded-full transition-all",
            checked ? "left-[18px] bg-accent" : "left-0.5 bg-subtle",
          )}
        />
      </button>
    </label>
  );
}

/* ---------------------------- Segmented control ---------------------------- */

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string; disabled?: boolean }>;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-base p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={cx(
            "h-7 rounded-md px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40",
            value === o.value ? "bg-overlay text-ink shadow-sm" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------------------- Stat ---------------------------- */

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: Tone }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-[0.08em] text-subtle">{label}</dt>
      <dd
        className={cx(
          "tnum mt-1 text-2xl font-semibold leading-none",
          tone === "accent" ? "text-accent" : tone === "warn" ? "text-warn" : "text-ink",
        )}
      >
        {value}
      </dd>
      {hint && <p className="mt-1.5 text-[11px] leading-snug text-subtle">{hint}</p>}
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
        <div className="absolute inset-y-0 w-1/3 rounded-full bg-accent [animation:indeterminate_1.4s_ease-in-out_infinite]" />
      ) : (
        <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${Math.round(ratio * 100)}%` }} />
      )}
    </div>
  );
}

/* ---------------------------- State views ---------------------------- */

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
  const ring = { neutral: "text-muted", accent: "text-accent", ok: "text-ok", warn: "text-warn", danger: "text-danger" }[tone];
  return (
    <div role={role} className="animate-rise flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <div className={cx("grid size-12 place-items-center rounded-xl border border-line-strong bg-raised", ring)}>{icon}</div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {description && <p className="max-w-md text-[13px] leading-relaxed text-muted">{description}</p>}
      {action && <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

/** DEMO / MOCK etiketi — sahte sonuç gösteren her alanda kullanılır. */
export function DemoBadge({ className }: { className?: string }) {
  return (
    <Badge tone="warn" className={cx("uppercase tracking-wider", className)} title="Bu değerler gerçek model çıktısı değildir.">
      Demo / Mock data
    </Badge>
  );
}
