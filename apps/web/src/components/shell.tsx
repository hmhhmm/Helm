"use client";

import {
  Banknote, BarChart3, Bot, CalendarClock, Command, HandCoins, Home, Languages, OctagonAlert, Scale, ShieldAlert, SlidersHorizontal,
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
    <div className="min-h-dvh md:grid md:grid-cols-[232px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[70] focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-contrast">{t("common.skip")}</a>
      <aside className="sticky top-3 m-3 mr-0 hidden h-[calc(100dvh-1.5rem)] rounded-3xl border border-border bg-surface shadow-card backdrop-blur-xl md:flex md:flex-col md:gap-1 md:p-4">
        <div className="mb-5 flex items-center gap-2.5 px-2 pt-1">
          <span aria-hidden className="grid size-9 place-items-center rounded-xl bg-grad text-lg font-extrabold text-white shadow-glow">H</span>
          <span className="text-xl font-bold tracking-tight">Helm</span>
        </div>
        <nav aria-label={t("nav.label")} className="flex flex-col gap-1">
          {NAV.map(({ href, key, Icon }) => (
            <Link
              key={href} href={href} aria-current={isActive(href) ? "page" : undefined}
              className={cn("flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-all duration-150",
                isActive(href) ? "bg-grad text-white shadow-glow" : "text-muted hover:bg-bg hover:text-text")}
            >
              <Icon aria-hidden className="size-4" />
              {t(key)}
            </Link>
          ))}
        </nav>
        <div className="mt-auto space-y-2 px-3 text-xs text-muted">
          <p className="font-semibold text-text">{t("bank.label")}</p>
          <p>{t("bank.note")}</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col pb-20 md:pb-0">
        <header className="sticky top-0 z-20 flex items-center gap-2 bg-bg/60 px-4 py-3 backdrop-blur-xl md:px-8">
          <span role="status" className="inline-flex min-h-8 min-w-0 items-center truncate rounded-full border border-border bg-surface px-3 text-[11px] font-semibold text-muted md:text-xs">
            {t("synthetic")}
          </span>
          <span className="hidden min-h-8 items-center rounded-full border border-border bg-surface px-3 text-xs font-semibold text-muted sm:inline-flex">{t("bank.label")}</span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={openSimulator} data-testid="date-control" aria-label={`${s ? flong(s.today, lang) : ""}. ${t("sim.open")}`}
              className="num inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm font-semibold hover:bg-bg"
            >
              <SlidersHorizontal aria-hidden className="size-4 text-accent" />
              <span className="hidden md:inline">{s ? flong(s.today, lang) : "…"}</span>
              <span className="md:hidden">{s ? fdate(s.today, lang) : "…"}</span>
            </button>
            <button onClick={openPalette} aria-label={t("palette.title")} className="hidden size-11 cursor-pointer items-center justify-center rounded-lg border border-border bg-surface hover:bg-bg md:inline-flex">
              <Command aria-hidden className="size-4" />
            </button>
            <button
              onClick={() => setLang(lang === "en" ? "ms" : "en")} aria-label={`${lang === "en" ? "BM" : "EN"}: ${t("lang.switch")}`}
              className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-xs font-bold hover:bg-bg"
            >
              <Languages aria-hidden className="size-4" />{lang === "en" ? "BM" : "EN"}
            </button>
            <ThemeToggle />
          </div>
        </header>

        {s?.kill_switch && (
          <div role="alert" className="flex items-center gap-2 bg-deny px-4 py-2 text-sm font-semibold text-white md:px-8">
            <OctagonAlert aria-hidden className="size-4" /> {t("banner.kill")}
          </div>
        )}
        {s && !s.chain_ok && (
          <div role="alert" className="flex items-center gap-2 bg-deny px-4 py-2 text-sm font-semibold text-white md:px-8" data-testid="chain-banner">
            <ShieldAlert aria-hidden className="size-4" /> {t("banner.chain", { row: s.chain_broken_at ?? "?" })}
          </div>
        )}
        {s?.demo_mode && <div className="bg-accent/10 px-4 py-1.5 text-center text-xs text-muted">{t("banner.demo")}</div>}

        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 md:px-8">{children}</main>
      </div>

      <nav aria-label={t("nav.label")} className="fixed inset-x-2 bottom-2 z-30 grid grid-cols-7 rounded-2xl border border-border bg-surface shadow-card backdrop-blur-xl md:hidden">
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
