"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Menu, ShieldAlert, X } from "lucide-react";
import { NAV_ITEMS } from "@/config/navigation";
import { useAnalysis } from "@/state/analysis-store";
import { Badge, DemoBadge, StatusDot, cx } from "@/components/ui/primitives";

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid size-8 place-items-center rounded-lg border border-accent/40 bg-accent-soft">
        <svg viewBox="0 0 24 24" className="size-4 text-accent" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" strokeLinecap="round" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="text-[13px] font-semibold tracking-[0.14em] text-ink">THERMA</div>
        <div className="text-[10px] font-medium tracking-[0.22em] text-accent">SEARCH AI</div>
      </div>
    </div>
  );
}

function SystemStatus() {
  const { service, health, capabilities } = useAnalysis();
  const mock = service.mode === "mock";
  const connected = health?.backendConnected === true;
  return (
    <div className="rounded-lg border border-line bg-raised p-3 text-xs" aria-label="Sistem durumu">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-subtle">Sistem durumu</div>
      <ul className="space-y-1.5">
        <li className="flex items-center justify-between gap-2">
          <span className="text-muted">API</span>
          <span className="flex items-center gap-1.5 text-ink">
            <StatusDot tone={mock ? "warn" : connected ? "ok" : "danger"} />
            {mock ? "Mock servis" : connected ? "Bağlı" : "Bağlı değil"}
          </span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-muted">Model</span>
          <span className="flex items-center gap-1.5 text-ink">
            <StatusDot tone="neutral" />
            {capabilities?.model && !mock ? capabilities.model.name : "Yüklü değil"}
          </span>
        </li>
      </ul>
      {mock && <p className="mt-2 border-t border-line pt-2 leading-snug text-subtle">Çıkarım yok. Gösterilen tespitler yapay demo verisidir.</p>}
    </div>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Ana gezinme" className="flex flex-col gap-1">
      {NAV_ITEMS.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cx(
              "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors",
              active ? "bg-overlay text-ink" : "text-muted hover:bg-raised hover:text-ink",
            )}
          >
            {active && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-accent" />}
            <Icon className={cx("size-[18px] shrink-0", active ? "text-accent" : "text-subtle group-hover:text-muted")} aria-hidden />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{item.label}</span>
              <span className="block truncate text-[11px] text-subtle">{item.description}</span>
            </span>
            {item.status === "planned" && <Badge className="shrink-0">Planlı</Badge>}
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Logo />
      <NavList onNavigate={onNavigate} />
      <div className="mt-auto space-y-3">
        <SystemStatus />
        <p className="px-1 text-[10px] leading-snug text-subtle">
          Karar destek aracıdır; otomatik tespitler insan doğrulaması gerektirir. v0.1 MVP iskeleti.
        </p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { service, health } = useAnalysis();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const current = NAV_ITEMS.find((n) => pathname.startsWith(n.href));

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const mock = service.mode === "mock";

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-base">
        İçeriğe geç
      </a>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-surface/95 backdrop-blur lg:block">
        <SidebarContent />
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Gezinme menüsü">
          <button type="button" aria-label="Menüyü kapat" className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          <aside className="animate-rise absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-line bg-surface">
            <button
              type="button"
              aria-label="Menüyü kapat"
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-3 grid size-8 place-items-center rounded-md text-muted hover:bg-raised"
            >
              <X className="size-4" />
            </button>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-base/80 px-4 backdrop-blur lg:px-6">
          <button
            type="button"
            aria-label="Menüyü aç"
            onClick={() => setDrawerOpen(true)}
            className="grid size-9 place-items-center rounded-lg border border-line text-muted hover:bg-raised lg:hidden"
          >
            <Menu className="size-4" />
          </button>
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-[0.14em] text-subtle">Operasyon merkezi</p>
            <h1 className="truncate text-sm font-semibold text-ink">{current?.label ?? "Therma Search AI"}</h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {mock && <DemoBadge className="max-sm:hidden" />}
            <Badge tone={mock ? "neutral" : health?.backendConnected ? "ok" : "danger"}>
              <StatusDot tone={mock ? "warn" : health?.backendConnected ? "ok" : "danger"} pulse={!mock} />
              {mock ? "Backend yok" : health?.backendConnected ? "Backend bağlı" : "Backend bağlı değil"}
            </Badge>
          </div>
        </header>

        {mock && (
          <div className="flex items-start gap-2 border-b border-warn/25 bg-warn-soft/50 px-4 py-2 text-xs text-warn sm:hidden">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>DEMO / MOCK DATA — gerçek model çıkarımı yok.</span>
          </div>
        )}

        <main id="main" className="mx-auto w-full max-w-[1600px] px-4 py-5 lg:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
