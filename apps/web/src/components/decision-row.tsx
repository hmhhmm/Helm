"use client";

import { ChevronRight } from "lucide-react";
import { useT } from "@/i18n";
import type { Row } from "@/lib/api";
import { daysBetween, fdate, rm } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Card } from "./ui/card";
import { VerdictBadge } from "./ui/verdict-badge";

/** A bordered list of payments: one dense row each, like a ledger. */
export function DecisionList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("overflow-hidden p-0", className)}>
      <ul className="divide-y divide-border">{children}</ul>
    </Card>
  );
}

/** One payment: payee and amount, verdict, release date, and a one-sentence reason. */
export function DecisionRow({ row, onOpen, compact }: { row: Row; onOpen: () => void; compact?: boolean }) {
  const { t, lang } = useT();
  const late = row.release_on && row.due ? daysBetween(row.due, row.release_on) : 0;
  const flipped = row.previous_verdict && row.previous_verdict !== row.verdict;
  const dateLine =
    row.status === "sent"
      ? t("row.sent", { date: fdate(row.sent_on, lang) })
      : row.status === "held_by_owner"
        ? t("decision.heldByYou")
        : row.verdict === "HOLD" && !row.release_on
          ? t("decision.noSafeDate")
          : row.verdict === "DENY"
            ? t("row.blocked")
            : row.verdict === "ESCALATE"
              ? t("row.waitingYou")
              : row.release_on
                ? t("row.payOn", { date: fdate(row.release_on, lang) }) + (late > 0 ? ` · ${t("decision.daysAfter", { n: late })}` : "")
                : "";
  return (
    <li>
      <button
        onClick={onOpen}
        className="group grid w-full cursor-pointer grid-cols-[1fr_auto] items-start gap-x-4 gap-y-1 px-4 py-3 text-left transition-colors duration-150 hover:bg-subtle"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{row.payee}</span>
          <span className="num block truncate text-xs text-muted">{row.ref ?? row.label} · {t("decision.due", { date: fdate(row.due, lang) })}</span>
        </span>
        <span className="num text-right text-sm font-semibold">{rm(row.amount)}</span>
        <span className="col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span key={`${row.verdict}-${row.release_on}`} className={cn(flipped && "stamp", "inline-block")}><VerdictBadge verdict={row.verdict} /></span>
          <span className="num text-[13px]">{dateLine}</span>
          {flipped && <span className="text-xs text-muted">{t("row.wasBefore", { was: t(`verdict.${row.previous_verdict!}`) })}</span>}
          {row.quarantined && <span className="rounded-md bg-deny/10 px-2 py-0.5 text-xs font-medium text-deny">{t("doc.quarantined")}</span>}
          <span className="ml-auto inline-flex items-center gap-0.5 text-xs font-medium text-accent">
            {t("row.seeWorking")} <ChevronRight aria-hidden className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </span>
        </span>
        {!compact && <span className="col-span-2 line-clamp-2 text-[13px] text-muted">{lang === "ms" ? row.why_ms : row.why}</span>}
      </button>
    </li>
  );
}
