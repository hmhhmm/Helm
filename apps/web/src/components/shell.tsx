"use client";

import {
  Banknote, BarChart3, Bot, CalendarClock, HandCoins, Home, Scale,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { en } from "@/i18n/en";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

const NAV = [
  { href: "/", label: en.nav.today, Icon: Home },
  { href: "/forecast", label: en.nav.forecast, Icon: BarChart3 },
  { href: "/payments", label: en.nav.payments, Icon: CalendarClock },
  { href: "/collections", label: en.nav.collections, Icon: HandCoins },
  { href: "/cash", label: en.nav.cash, Icon: Banknote },
  { href: "/policy", label: en.nav.policy, Icon: Scale },
  { href: "/agents", label: en.nav.agents, Icon: Bot },
];

function useActive() {
  const pathname = usePathname();
  return (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
}

export function Shell({ children }: { children: React.ReactNode }) {
  const isActive = useActive();
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[232px_1fr]">
      <aside className="hidden border-r border-border bg-surface md:flex md:flex-col md:gap-1 md:p-4">
        <div className="mb-4 px-3 text-xl font-bold tracking-tight">{en.brand}</div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium",
                isActive(href) ? "bg-accent text-accent-contrast" : "text-muted hover:bg-bg hover:text-text",
              )}
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto px-3 text-xs text-muted">{en.demoBank}</p>
      </aside>

      <div className="flex min-w-0 flex-col pb-20 md:pb-0">
        <header className="flex items-center justify-between gap-3 px-4 py-3 md:px-8">
          <span
            className="inline-flex min-h-8 items-center rounded-full border border-border bg-surface px-3 text-xs font-semibold text-muted"
            role="status"
          >
            {en.synthetic}
          </span>
          <ThemeToggle />
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 pb-8 md:px-8">{children}</main>
      </div>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-7 border-t border-border bg-surface md:hidden"
      >
        {NAV.map(({ href, label, Icon }) => (
          <Link
            key={href}
            href={href}
            aria-current={isActive(href) ? "page" : undefined}
            className={cn(
              "flex min-h-14 flex-col items-center justify-center gap-0.5 px-0.5 text-[10px] font-medium",
              isActive(href) ? "text-accent" : "text-muted",
            )}
          >
            <Icon aria-hidden className="size-5" />
            <span className="max-w-full truncate">{label.split(" ")[0]}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}
