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
  const [confirming, setConfirming] = useState(false);
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

  const lowPoint = c.low_point_if_paid;
  return (
    <div className="space-y-5">
      <div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-escalate/10 px-2.5 py-1 text-xs font-medium text-escalate"><ShieldAlert aria-hidden className="size-3.5" />{t("approval.needsOk")}</span>
        <p className="num mt-3 text-4xl font-semibold tracking-tight">{rm(d.row.amount)}</p>
      </div>

      <dl className="divide-y divide-border rounded-lg border border-border bg-surface text-sm">
        <Line label={t("approval.payee")} value={d.row.payee} />
        {d.row.ref && <Line label={t("approval.reference")} value={d.row.ref} mono />}
        {d.row.due && <Line label={t("approval.dueOn")} value={fdate(d.row.due, lang)} />}
      </dl>

      {d.row.quarantined && (
        <div className="rounded-lg border border-deny/40 bg-deny/10 p-3 text-sm">
          <b>{t("approval.warnTitle")}</b> {t("approval.warnBody")}
        </div>
      )}

      {d.row.kind === "pay_bill" && (
        <section aria-label={t("approval.check")}>
          <h3 className="mb-2 text-sm font-semibold">{t("approval.check")}</h3>
          <div className="grid grid-cols-2 gap-3">
            <Tile label={t("approval.ifPaid")} value={pct(c.p_if_paid ?? 0)} note={t("approval.stay", { min: rm(d.min_balance) })} />
            <Tile label={t("approval.ifHeld")} value={pct(c.p_if_held ?? 0)} note={t("approval.nothingMoves")} />
          </div>
          {lowPoint && <p className="num mt-2 text-[13px] text-muted">{t("approval.lowest", { rm: rm(lowPoint.rm), date: fdate(lowPoint.date, lang) })}</p>}
          {c.safe_date && <p className="mt-1 text-[13px] text-muted">{t("approval.safeDate", { date: fdate(c.safe_date, lang) })}</p>}
        </section>
      )}

      {asked && (
        <section className="rounded-lg bg-subtle p-3">
          <h3 className="mb-1 text-sm font-semibold">{t("approval.whyTitle")}</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {failing.length ? failing.map((f) => <li key={f.rule}>{reasonFor(f.rule, t)}</li>) : <li>{d.row.why}</li>}
          </ul>
          <p className="mt-2 text-[13px] text-muted">{lang === "ms" ? d.row.why_ms : d.row.why}</p>
        </section>
      )}

      {phase !== "ask" && (
        <div role="status" className={`rounded-lg border p-3 text-sm ${phase === "approved" ? "border-allow/40 bg-allow/10" : "border-border bg-subtle"}`}>
          <p className="mb-0.5 font-semibold">{phase === "approved" ? t("approval.youApprove") : t("approval.youHold")}</p>
          <p>{phase === "approved" ? t("approval.approved") : t("approval.held")}</p>
        </div>
      )}

      {waiting && !confirming && (
        <div className="space-y-2">
          <Button variant="success" className="w-full min-h-12 text-[15px]" disabled={act.isPending} onClick={() => (d.row.quarantined ? setConfirming(true) : act.mutate("approve"))}><Check aria-hidden className="size-4" />{t("approval.approve")}</Button>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="secondary" disabled={act.isPending} onClick={() => act.mutate("hold")}><Pause aria-hidden className="size-4" />{t("approval.hold")}</Button>
            <Button variant="secondary" onClick={() => setAsked(true)}><HelpCircle aria-hidden className="size-4" />{t("approval.ask")}</Button>
          </div>
        </div>
      )}
      {waiting && confirming && (
        <div className="rounded-lg border border-deny/40 bg-deny/10 p-3">
          <p className="text-sm font-semibold">{t("approval.confirm")}</p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="danger" disabled={act.isPending} onClick={() => act.mutate("approve")} data-testid="approve-anyway">{t("approval.confirmYes")}</Button>
            <Button size="sm" variant="secondary" onClick={() => setConfirming(false)}>{t("approval.cancel")}</Button>
          </div>
        </div>
      )}
      {!waiting && phase === "ask" && <p className="text-sm text-muted">{t("approval.notWaiting")}</p>}
    </div>
  );
}

function Line({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-3.5 py-2.5">
      <dt className="text-muted">{label}</dt>
      <dd className={`min-w-0 truncate text-right font-medium ${mono ? "num" : ""}`}>{value}</dd>
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="num mt-1 text-2xl font-semibold">{value}</p>
      <p className="mt-0.5 text-xs text-muted">{note}</p>
    </div>
  );
}

function reasonFor(rule: string, t: ReturnType<typeof useT>["t"]): string {
  switch (rule) {
    case "duplicate_or_anomaly": return t("approval.reason.anomaly");
    case "approval_limit": return t("approval.reason.limit");
    case "protected_payee": return t("approval.reason.protected");
    case "min_balance_chance": return t("approval.reason.chance");
    default: return t("approval.reason.other");
  }
}
