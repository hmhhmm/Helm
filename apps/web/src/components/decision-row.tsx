"use client";

import { ChevronRight } from "lucide-react";
import { useT } from "@/i18n";
import type { Row } from "@/lib/api";
import { daysBetween, fdate, rm } from "@/lib/format";
import { cn } from "@/lib/utils";
import { VerdictBadge } from "./ui/verdict-badge";

/** One payment: verdict chip, release date, one-sentence why, and a 'see working' link. */
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
        className="group flex w-full cursor-pointer flex-col gap-2 rounded-card border border-border bg-surface p-4 text-left shadow-card transition-colors duration-150 hover:border-accent/60"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-semibold">{row.payee}</p>
            <p className="num truncate text-xs text-muted">{row.ref ?? row.label} · {t("decision.due", { date: fdate(row.due, lang) })}</p>
          </div>
          <p className="num shrink-0 text-lg font-bold">{rm(row.amount)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span key={`${row.verdict}-${row.release_on}`} className={cn(flipped && "stamp", "inline-block")}><VerdictBadge verdict={row.verdict} /></span>
          <span className="num text-sm font-medium">{dateLine}</span>
          {flipped && <span className="text-xs text-muted">{t("row.wasBefore", { was: t(`verdict.${row.previous_verdict!}`) })}</span>}
          {row.quarantined && <span className="rounded-full border border-deny/40 bg-deny/10 px-2 py-0.5 text-xs font-semibold text-deny">{t("doc.quarantined")}</span>}
        </div>
        {!compact && <p className="line-clamp-2 text-sm text-muted">{lang === "ms" ? row.why_ms : row.why}</p>}
        <span className="inline-flex items-center gap-1 text-sm font-semibold text-accent">
          {t("row.seeWorking")} <ChevronRight aria-hidden className="size-4 transition-transform group-hover:translate-x-0.5" />
        </span>
      </button>
    </li>
  );
}
