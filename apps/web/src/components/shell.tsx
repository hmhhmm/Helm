"use client";

import {
  Banknote, BarChart3, Bot, CalendarClock, HandCoins, Home, Languages, OctagonAlert, Scale, Search, ShieldAlert, SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { useT, type Key } from "@/i18n";
import { fdate, flong } from "@/lib/format";
import { useAppState } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { useOverlays } from "./overlays";
import { ThemeToggle } from "./theme-toggle";

const NAV: { href: string; key: Key; short: Key; Icon: typeof Home }[] = [
  { href: "/", key: "nav.today", short: "nav.today", Icon: Home },
  { href: "/forecast", key: "nav.forecast", short: "nav.forecast.short", Icon: BarChart3 },
  { href: "/payments", key: "nav.payments", short: "nav.payments.short", Icon: CalendarClock },
  { href: "/collections", key: "nav.collections", short: "nav.collections.short", Icon: HandCoins },
  { href: "/cash", key: "nav.cash", short: "nav.cash", Icon: Banknote },
  { href: "/policy", key: "nav.policy", short: "nav.policy", Icon: Scale },
  { href: "/agents", key: "nav.agents", short: "nav.agents.short", Icon: Bot },
];

const GROUPS: { label: Key; items: typeof NAV }[] = [
  { label: "nav.group.overview", items: NAV.slice(0, 2) },
  { label: "nav.group.money", items: NAV.slice(2, 5) },
  { label: "nav.group.control", items: NAV.slice(5) },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang } = useT();
  const pathname = usePathname();
  const state = useAppState();
  const { openSimulator, openPalette } = useOverlays();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const s = state.data;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openPalette]);

  if (pathname.startsWith("/approve/")) return <>{children}</>;

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[248px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[70] focus:rounded focus:bg-accent-solid focus:px-3 focus:py-2 focus:text-on-accent">{t("common.skip")}</a>
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-border bg-surface md:flex">
        <div className="flex h-16 items-center px-6">
          <span className="text-lg font-semibold tracking-tight">Helm</span>
        </div>
        <nav aria-label={t("nav.label")} className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 pb-4 pt-2">
          {GROUPS.map((g) => (
            <div key={g.label}>
              <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted">{t(g.label)}</p>
              <div className="flex flex-col gap-0.5">
                {g.items.map(({ href, key, Icon }) => (
                  <Link
                    key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
                    className={cn("relative flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-150",
                      isActive(href) ? "bg-subtle text-text" : "text-muted hover:bg-subtle hover:text-text")}
                  >
                    {isActive(href) && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-accent-solid" />}
                    <Icon aria-hidden className={cn("size-[18px]", isActive(href) && "text-accent")} />
                    {t(key)}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
            <span aria-hidden className="grid size-8 place-items-center rounded-full bg-subtle text-xs font-semibold text-muted">WP</span>
            <span className="min-w-0 text-[13px] font-medium leading-tight">Warisan Printing</span>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col pb-16 md:pb-0">
        <header className="sticky top-0 z-20 flex min-h-16 items-center gap-3 border-b border-border bg-bg px-4 py-2 md:px-8">
          <span className="text-base font-semibold tracking-tight md:hidden">Helm</span>
          <button onClick={openPalette} className="hidden h-10 w-full max-w-xl cursor-pointer items-center justify-between rounded-lg border border-border bg-surface px-3.5 text-sm text-muted hover:bg-subtle md:flex">
            <span className="flex items-center gap-2.5"><Search aria-hidden className="size-4" />{t("palette.search")}</span>
            <kbd className="rounded border border-border px-1.5 text-[11px]">⌘K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={openSimulator} data-testid="date-control" aria-label={`${s ? flong(s.today, lang) : ""}. ${t("sim.open")}`}
              className="num inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap rounded-lg border border-border bg-surface px-3 text-[13px] font-medium hover:bg-subtle md:min-h-10"
            >
              <SlidersHorizontal aria-hidden className="hidden size-4 text-muted sm:block" />
              <span className="hidden md:inline">{s ? flong(s.today, lang) : "…"}</span>
              <span className="md:hidden">{s ? fdate(s.today, lang) : "…"}</span>
            </button>
            <button
              onClick={() => setLang(lang === "en" ? "ms" : "en")} aria-label={`${lang === "en" ? "BM" : "EN"}: ${t("lang.switch")}`}
              className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-xs font-semibold hover:bg-subtle md:min-h-10"
            >
              <Languages aria-hidden className="size-4 text-muted" />{lang === "en" ? "BM" : "EN"}
            </button>
            <ThemeToggle />
          </div>
        </header>

        {s?.kill_switch && (
          <div role="alert" className="flex items-center gap-2 bg-deny px-4 py-2 text-sm font-medium text-white md:px-8">
            <OctagonAlert aria-hidden className="size-4" /> {t("banner.kill")}
          </div>
        )}
        {s && !s.chain_ok && (
          <div role="alert" className="flex items-center gap-2 bg-deny px-4 py-2 text-sm font-medium text-white md:px-8" data-testid="chain-banner">
            <ShieldAlert aria-hidden className="size-4" /> {t("banner.chain", { row: s.chain_broken_at ?? "?" })}
          </div>
        )}
        {s?.demo_mode && <div className="border-b border-border bg-subtle px-4 py-1.5 text-center text-xs text-muted">{t("banner.demo")}</div>}

        <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 md:px-8">{children}</main>
        <footer className="mx-auto w-full max-w-[1200px] px-4 pb-6 text-xs text-muted md:px-8">{t("synthetic")} · {t("bank.label")}</footer>
      </div>

      <nav aria-label={t("nav.label")} className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-7 border-t border-border bg-surface md:hidden">
        {NAV.map(({ href, short, Icon }) => (
          <Link
            key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
            className={cn("flex min-h-14 flex-col items-center justify-center gap-0.5 px-0.5 text-[10px] font-medium", isActive(href) ? "text-accent" : "text-muted")}
          >
            <Icon aria-hidden className="size-5" />
            <span className="max-w-full truncate">{t(short)}</span>
            {isActive(href) && <span className="sr-only">{t("nav.current")}</span>}
          </Link>
        ))}
      </nav>
    </div>
  );
}
