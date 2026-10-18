"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Check, Pause, HelpCircle, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useT } from "@/i18n";
import { api, unwrap } from "@/lib/api";
import { fdate, pct, rm } from "@/lib/format";
import { useAct, useDecision } from "@/lib/hooks";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/card";

type Phase = "ask" | "approved" | "held";

/** A chat-style card for approving an ESCALATE from a phone. Not affiliated with any messaging app. */
export function ApprovalCard({ id, onDone }: { id: string; onDone?: () => void }) {
  const { t, lang } = useT();
  const q = useDecision(id);
  const qc = useQueryClient();
  const [phase, setPhase] = useState<Phase>("ask");
  const [asked, setAsked] = useState(false);
  const act = useAct(async (choice: "approve" | "hold") => {
    unwrap(await api.POST("/decisions/{proposal_id}/owner", { params: { path: { proposal_id: id } }, body: { choice } }));
    setPhase(choice === "approve" ? "approved" : "held");
    await qc.invalidateQueries();
    onDone?.();
  });

  if (q.isPending) return <div className="space-y-3 p-2"><Skeleton className="h-24" /><Skeleton className="h-16" /></div>;
  if (q.isError) return <p role="alert" className="p-4 text-sm">{t("error.title")}: {(q.error as Error).message}</p>;
  const d = q.data;
  const c = d.consequence as { p_if_paid?: number; p_if_held?: number; low_point_if_paid?: { date: string; rm: number }; safe_date?: string | null };
  const waiting = d.row.verdict === "ESCALATE" && d.row.status === "queued" && phase === "ask";
  const failing = d.checks.filter((x) => x.result === "fail" || x.result === "flag");

  return (
    <div className="space-y-2 rounded-card p-3" style={{ background: "var(--chat-bg)" }}>
      <div className="flex items-center gap-3 rounded-lg bg-surface/80 px-3 py-2">
        <span aria-hidden className="grid size-9 place-items-center rounded-full bg-accent font-bold text-accent-contrast">H</span>
        <div className="leading-tight">
          <p className="font-semibold">Helm</p>
          <p className="text-xs text-muted">{t("approval.sub")}</p>
        </div>
      </div>

      <Bubble>
        <p className="mb-1 flex items-center gap-1.5 text-sm font-semibold text-escalate"><ShieldAlert aria-hidden className="size-4" />{t("approval.needsOk")}</p>
        <p className="text-base font-bold">{t("approval.pay", { payee: d.row.payee, amount: rm(d.row.amount) })}</p>
        <p className="text-sm text-muted">{d.row.ref} · {t("approval.due", { date: fdate(d.row.due, lang) })}</p>
      </Bubble>

      {d.row.quarantined && (
        <Bubble tone="warn">
          <p className="text-sm"><b>{t("approval.warnTitle")}</b> {t("approval.warnBody")}</p>
        </Bubble>
      )}

      <Bubble>
        <p className="text-sm">
          <b>{t("approval.ifPaid")}</b>{" "}
          {t("approval.chance", { p: pct(c.p_if_paid ?? 0), min: rm(d.min_balance) })}
          {c.low_point_if_paid && " " + t("approval.lowest", { rm: rm(c.low_point_if_paid.rm), date: fdate(c.low_point_if_paid.date, lang) })}
        </p>
        <p className="mt-2 text-sm">
          <b>{t("approval.ifHeld")}</b> {t("approval.chance", { p: pct(c.p_if_held ?? 0), min: rm(d.min_balance) })} {t("approval.nothingMoves")}
        </p>
        {c.safe_date && <p className="mt-2 text-sm text-muted">{t("approval.safeDate", { date: fdate(c.safe_date, lang) })}</p>}
      </Bubble>

      {asked && (
        <Bubble>
          <p className="mb-1 text-sm font-semibold">{t("approval.whyTitle")}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {failing.length ? failing.map((f) => <li key={f.rule}>{reasonFor(f.rule, t)}</li>) : <li>{d.row.why}</li>}
          </ul>
          <p className="mt-2 text-sm text-muted">{lang === "ms" ? d.row.why_ms : d.row.why}</p>
        </Bubble>
      )}

      {phase !== "ask" && (
        <>
          <Bubble self>{phase === "approved" ? t("approval.youApprove") : t("approval.youHold")}</Bubble>
          <Bubble tone={phase === "approved" ? "ok" : "plain"}>
            <p className="text-sm">{phase === "approved" ? t("approval.approved") : t("approval.held")}</p>
          </Bubble>
        </>
      )}

      {waiting && (
        <div className="grid grid-cols-3 gap-2 pt-1">
          <Button variant="success" disabled={act.isPending} onClick={() => act.mutate("approve")}><Check aria-hidden className="size-4" />{t("approval.approve")}</Button>
          <Button variant="secondary" disabled={act.isPending} onClick={() => act.mutate("hold")}><Pause aria-hidden className="size-4" />{t("approval.hold")}</Button>
          <Button variant="ghost" className="bg-surface/70" onClick={() => setAsked(true)}><HelpCircle aria-hidden className="size-4" />{t("approval.ask")}</Button>
        </div>
      )}
      {!waiting && phase === "ask" && (
        <Bubble><p className="text-sm text-muted">{t("approval.notWaiting")}</p></Bubble>
      )}
    </div>
  );
}

function reasonFor(rule: string, t: ReturnType<typeof useT>["t"]): string {
  switch (rule) {
    case "duplicate_or_anomaly": return t("approval.reason.anomaly");
    case "approval_limit": return t("approval.reason.limit");
    case "protected_payee": return t("approval.reason.protected");
    default: return t("approval.reason.other");
  }
}

function Bubble({ children, self, tone = "plain" }: { children: React.ReactNode; self?: boolean; tone?: "plain" | "warn" | "ok" }) {
  const toneCls = tone === "warn" ? "border-deny/40 bg-deny/10" : tone === "ok" ? "border-allow/40 bg-allow/10" : "border-transparent";
  return (
    <div className={`rise flex ${self ? "justify-end" : ""}`}>
      <div className={`max-w-[92%] rounded-xl border px-3 py-2 shadow-sm ${self ? "bg-accent text-accent-contrast" : "bg-surface"} ${toneCls}`}>{children}</div>
    </div>
  );
}
