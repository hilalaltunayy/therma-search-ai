"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { NAV_ITEMS, type NavItem } from "@/config/navigation";
import { useAnalysis } from "@/state/analysis-store";
import { Badge, StatusDot, Tooltip, cx } from "@/components/ui/primitives";

function BrandMark({ size = 40 }: { size?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-xl bg-[linear-gradient(145deg,#BD6542_0%,#7556B8_100%)] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.12),0_8px_20px_-10px_rgb(189_101_66/0.7)]"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="#fff" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 2v4M12 18v4M2 12h4M18 12h4" strokeLinecap="round" />
      </svg>
    </span>
  );
}

function useSystemStatus() {
  const { service, health, capabilities } = useAnalysis();
  const mock = service.mode === "mock";
  const connected = health?.backendConnected === true;
  const modelLoaded = !mock && health?.modelLoaded === true;
  return {
    mock,
    api: mock
      ? { tone: "neutral" as const, text: "API bağlı değil", hint: "Mock servis çalışıyor; backend çağrısı yapılmaz." }
      : connected
        ? { tone: "cyan" as const, text: "API bağlı", hint: "FastAPI sağlık kontrolü başarılı." }
        : { tone: "danger" as const, text: "API ulaşılamıyor", hint: "HTTP modunda backend yanıt vermiyor." },
    model: modelLoaded
      ? { tone: "cyan" as const, text: capabilities?.model?.name ?? "Model yüklü", hint: "Backend'in bildirdiği aktif model." }
      : { tone: "neutral" as const, text: "Model yüklenmedi", hint: mock ? "Mock modunda model yoktur." : "Backend model bilgisi bildirmedi." },
  };
}

/** Rayın altındaki kompakt sistem durumu. */
function RailStatus() {
  const s = useSystemStatus();
  return (
    <div className="mt-auto flex flex-col items-center gap-2.5 pb-1" aria-label="Sistem durumu">
      <Tooltip label={s.mock ? "Mod: DEMO / MOCK" : "Mod: gerçek servis (HTTP)"} side="right">
        <span tabIndex={0} aria-label={s.mock ? "Mod: DEMO / MOCK" : "Mod: gerçek servis"} className="flex flex-col items-center gap-1 rounded-md px-1 font-mono text-[10.5px] font-semibold tracking-wider text-subtle">
          <StatusDot tone={s.mock ? "amber" : "cyan"} />
          {s.mock ? "MOCK" : "LIVE"}
        </span>
      </Tooltip>
      <Tooltip label={s.api.text} side="right">
        <span tabIndex={0} aria-label={s.api.text} className="flex flex-col items-center gap-1 rounded-md px-1 font-mono text-[10.5px] font-semibold tracking-wider text-subtle">
          <StatusDot tone={s.api.tone} />
          API
        </span>
      </Tooltip>
    </div>
  );
}

function RailLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;
  const planned = item.status === "planned";
  const label = planned ? `${item.label} · Planlı` : item.label;
  return (
    <Tooltip label={label} side="right">
      <Link
        href={item.href}
        aria-label={label}
        aria-current={active ? "page" : undefined}
        className={cx(
          "relative grid size-12 place-items-center rounded-xl transition-[background-color,color,box-shadow] duration-200 ease-out",
          active
            ? "bg-cyan-soft text-cyan shadow-[inset_0_0_0_1px_rgb(34_201_217/0.3)]"
            : planned
              ? "text-disabled hover:bg-raised/70 hover:text-muted"
              : "text-subtle hover:bg-raised/70 hover:text-ink",
        )}
      >
        {active && <span aria-hidden className="absolute -left-3 top-3 bottom-3 w-[3px] rounded-full bg-cyan" />}
        <Icon className="size-5" aria-hidden />
        {planned && <span aria-hidden className="absolute bottom-1.5 right-1.5 size-1.5 rounded-full bg-disabled" />}
      </Link>
    </Tooltip>
  );
}

function ExpandedNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Ana gezinme (genişletilmiş)" className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cx(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-200",
              active ? "bg-cyan-soft text-ink shadow-[inset_0_0_0_1px_rgb(34_201_217/0.3)]" : "text-muted hover:bg-raised/70 hover:text-ink",
            )}
          >
            <Icon className={cx("size-5 shrink-0", active ? "text-cyan" : "text-subtle")} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{item.label}</span>
              <span className="block truncate text-[12.5px] text-subtle">{item.description}</span>
            </span>
            {item.status === "planned" && <Badge className="h-6 px-2 text-xs">Planlı</Badge>}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const status = useSystemStatus();
  const [expanded, setExpanded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const current = NAV_ITEMS.find((n) => pathname.startsWith(n.href));

  useEffect(() => {
    if (!expanded && !drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setExpanded(false);
        setDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, drawerOpen]);

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-cyan focus:px-3 focus:py-2 focus:text-[#04121A]">
        İçeriğe geç
      </a>

      {/* 72 px ikon rayı (masaüstü) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col items-center gap-2 border-r border-line bg-base/85 py-3.5 backdrop-blur-md lg:flex">
        <Link href="/workspace" aria-label="Therma Search AI ana sayfa" className="mb-3 rounded-xl">
          <BrandMark />
        </Link>
        <nav aria-label="Ana gezinme" className="flex flex-col items-center gap-1.5">
          {NAV_ITEMS.map((item) => (
            <RailLink key={item.href} item={item} active={pathname.startsWith(item.href)} />
          ))}
        </nav>
        <Tooltip label={expanded ? "Menüyü daralt" : "Menüyü genişlet"} side="right">
          <button
            type="button"
            aria-label={expanded ? "Menüyü daralt" : "Menüyü genişlet"}
            aria-expanded={expanded}
            aria-controls="expanded-nav"
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 grid size-10 place-items-center rounded-xl text-subtle transition-colors duration-200 hover:bg-raised/70 hover:text-ink"
          >
            {expanded ? <PanelLeftClose className="size-[18px]" /> : <PanelLeftOpen className="size-[18px]" />}
          </button>
        </Tooltip>
        <RailStatus />
      </aside>

      {/* Genişletilmiş menü: rayın yanına açılan cam panel (içeriği itmez) */}
      {expanded && (
        <>
          <button type="button" aria-label="Menüyü kapat" tabIndex={-1} className="fixed inset-0 z-30 hidden cursor-default lg:block" onClick={() => setExpanded(false)} />
          <div id="expanded-nav" className="glass glass-edge animate-rise fixed bottom-3 left-[80px] top-3 z-40 hidden w-72 rounded-2xl p-4 lg:block">
            <p className="mb-3 px-1 text-xs font-semibold uppercase tracking-[0.12em] text-subtle">Therma Search AI</p>
            <ExpandedNav onNavigate={() => setExpanded(false)} />
          </div>
        </>
      )}

      {/* Mobil çekmece */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Gezinme menüsü">
          <button type="button" aria-label="Menüyü kapat" className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          <div className="glass animate-rise absolute inset-y-0 left-0 flex w-80 max-w-[86vw] flex-col gap-5 p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2.5">
                <BrandMark size={36} />
                <span className="text-sm font-semibold tracking-[0.12em]">THERMA SEARCH AI</span>
              </span>
              <button type="button" aria-label="Menüyü kapat" onClick={() => setDrawerOpen(false)} className="grid size-11 place-items-center rounded-xl text-muted hover:bg-raised">
                <X className="size-5" />
              </button>
            </div>
            <ExpandedNav onNavigate={() => setDrawerOpen(false)} />
            <div className="mt-auto space-y-2 rounded-xl border border-line p-3 text-[13px]">
              <p className="flex items-center justify-between"><span className="text-subtle">Mod</span><span className="flex items-center gap-2"><StatusDot tone={status.mock ? "amber" : "cyan"} />{status.mock ? "DEMO / MOCK" : "Gerçek servis"}</span></p>
              <p className="flex items-center justify-between"><span className="text-subtle">API</span><span className="flex items-center gap-2"><StatusDot tone={status.api.tone} />{status.api.text}</span></p>
              <p className="flex items-center justify-between"><span className="text-subtle">Model</span><span className="flex items-center gap-2"><StatusDot tone={status.model.tone} />{status.model.text}</span></p>
            </div>
          </div>
        </div>
      )}

      <div className="lg:pl-[72px]">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-base/75 px-4 backdrop-blur-md lg:px-6">
          <button
            type="button"
            aria-label="Menüyü aç"
            onClick={() => setDrawerOpen(true)}
            className="grid size-11 place-items-center rounded-xl border border-line-strong text-muted transition-colors hover:bg-raised lg:hidden"
          >
            <Menu className="size-5" />
          </button>
          <div className="min-w-0">
            <p className="hidden text-xs font-medium uppercase tracking-[0.12em] text-subtle sm:block">Therma Search AI · Operasyon</p>
            <h1 className="truncate text-[15px] font-semibold text-ink">{current?.label ?? "Therma Search AI"}</h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {status.mock && (
              <Tooltip label="Tüm sonuçlar yapay demo verisidir" side="bottom-end">
                <Badge tone="amber" tabIndex={0} className="font-semibold tracking-wide">
                  <StatusDot tone="amber" /> DEMO / MOCK
                </Badge>
              </Tooltip>
            )}
            <span className="hidden items-center gap-2 md:flex">
              <Tooltip label={status.api.hint} side="bottom-end">
                <Badge tabIndex={0} tone={status.api.tone}>
                  <StatusDot tone={status.api.tone} /> {status.api.text}
                </Badge>
              </Tooltip>
              <Tooltip label={status.model.hint} side="bottom-end">
                <Badge tabIndex={0} tone={status.model.tone}>
                  <StatusDot tone={status.model.tone} /> {status.model.text}
                </Badge>
              </Tooltip>
            </span>
          </div>
        </header>

        <main id="main">{children}</main>
      </div>
    </div>
  );
}
