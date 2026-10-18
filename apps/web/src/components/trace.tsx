"use client";

import { Check, ChevronDown, Flag, Minus, ShieldAlert, TriangleAlert, X } from "lucide-react";
import { useState } from "react";
import { useT, type Key } from "@/i18n";
import type { Schemas } from "@/lib/api";
import { fdate, pct, rm } from "@/lib/format";
import { cn } from "@/lib/utils";

type Check = Schemas["Check"] & Record<string, unknown>;

const RESULT_UI: Record<string, { icon: typeof Check; cls: string; word: Key }> = {
  pass: { icon: Check, cls: "text-allow", word: "trace.passed" },
  fail: { icon: X, cls: "text-deny", word: "trace.failed" },
  flag: { icon: Flag, cls: "text-escalate", word: "trace.flagged" },
  warn: { icon: TriangleAlert, cls: "text-hold", word: "trace.warning" },
  skip: { icon: Minus, cls: "text-muted", word: "trace.skipped" },
};

const TITLE: Record<string, Key> = {
  kill_switch: "trace.kill_switch",
  statutory_first: "trace.statutory_first",
  protected_payee: "trace.protected_payee",
  duplicate_or_anomaly: "trace.duplicate_or_anomaly",
  approval_limit: "trace.approval_limit",
  min_balance_chance: "trace.min_balance_chance",
  reserve_covers: "trace.reserve_covers",
};

export function Trace({ checks, minBalance }: { checks: Check[]; minBalance: number }) {
  const { t, lang } = useT();
  const [numbers, setNumbers] = useState(false);

  function sentence(c: Check): string {
    const num = (k: string) => (typeof c[k] === "number" ? (c[k] as number) : 0);
    switch (c.rule) {
      case "kill_switch":
        return c.result === "pass" ? t("trace.kill_switch.pass") : t("trace.kill_switch.fail");
      case "statutory_first":
        return t("trace.statutory_first.text");
      case "protected_payee":
        return c.result === "fail" ? t("trace.protected_payee.fail") : t("trace.protected_payee.pass");
      case "duplicate_or_anomaly": {
        if (c.result === "fail") return t("trace.duplicate.fail");
        const an = (c.anomalies as string[] | undefined) ?? [];
        if (an.length) return an.map((a) => t(`trace.anomaly.${a}` as Key)).join("; ");
        return t("trace.duplicate.pass");
      }
      case "approval_limit":
        return c.result === "fail"
          ? t("trace.approval_limit.fail", { amount: rm(num("amount")), limit: rm(num("limit")) })
          : t("trace.approval_limit.pass");
      case "min_balance_chance": {
        const low = c.low_point as { date: string; rm: number } | undefined;
        const p = num("p_ok");
        const req = num("required");
        if (c.result === "pass") return t("trace.chance.pass", { p: pct(p), min: rm(minBalance), req: pct(req) });
        const lowTxt = low ? t("trace.chance.low", { rm: rm(low.rm), date: fdate(low.date, lang) }) : "";
        return c.result === "warn"
          ? t("trace.chance.warn", { p: pct(p), min: rm(minBalance), low: lowTxt })
          : t("trace.chance.fail", { p: pct(p), req: pct(req), min: rm(minBalance), low: lowTxt });
      }
      case "reserve_covers":
        return t("trace.reserve_covers.fail", { reserve: rm(num("reserve")) });
      default:
        return "";
    }
  }

  return (
    <div>
      <ol className="space-y-2">
        {checks.map((c, i) => {
          const ui = RESULT_UI[c.result] ?? RESULT_UI.skip;
          const Icon = c.rule === "protected_payee" && c.result === "fail" ? ShieldAlert : ui.icon;
          return (
            <li key={`${c.rule}-${i}`} className="rise flex gap-3 rounded-lg border border-border bg-surface p-3" style={{ animationDelay: `${i * 30}ms` }}>
              <Icon aria-hidden className={cn("mt-0.5 size-5 shrink-0", ui.cls)} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="font-semibold">{t(TITLE[c.rule] ?? "trace.kill_switch")}</span>
                  <span className={cn("text-xs font-semibold uppercase tracking-wide", ui.cls)}>{t(ui.word)}</span>
                </div>
                <p className="mt-0.5 text-sm text-muted">{sentence(c)}</p>
                {numbers && (
                  <dl className="num mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded bg-bg p-2 text-xs">
                    {Object.entries(c)
                      .filter(([k]) => k !== "rule" && k !== "result")
                      .map(([k, v]) => (
                        <div key={k} className="contents">
                          <dt className="text-muted">{k}</dt>
                          <dd className="break-words">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                        </div>
                      ))}
                  </dl>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <button
        onClick={() => setNumbers((n) => !n)}
        aria-expanded={numbers}
        className="mt-3 inline-flex min-h-11 cursor-pointer items-center gap-1 text-sm font-semibold text-accent"
      >
        <ChevronDown aria-hidden className={cn("size-4 transition-transform", numbers && "rotate-180")} />
        {numbers ? t("trace.hideNumbers") : t("trace.showNumbers")}
      </button>
    </div>
  );
}
