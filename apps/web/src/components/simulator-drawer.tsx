"use client";

import { CalendarPlus, Clock, Mail, RotateCcw, Wrench } from "lucide-react";
import { useState } from "react";
import { useT, type Key } from "@/i18n";
import { api, unwrap } from "@/lib/api";
import { fdate, flong, pct, rm } from "@/lib/format";
import { useAct, useAppState } from "@/lib/hooks";
import { useOverlays } from "./overlays";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Sheet } from "./ui/sheet";
import { VerdictBadge } from "./ui/verdict-badge";

type Flip = { payee: string; amount: number; from: string; to: string; release_from?: string | null; release_to?: string | null };
type Result =
  | { kind: "advance"; message: string; data: Record<string, unknown> }
  | { kind: "late"; message: string; data: Record<string, unknown> }
  | { kind: "malicious"; message: string; data: Record<string, unknown> };

export function SimulatorDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, lang } = useT();
  const { data: state } = useAppState();
  const { openApproval } = useOverlays();
  const [result, setResult] = useState<Result | null>(null);

  const advance = useAct(async () => {
    const r = unwrap(await api.POST("/sim/advance-week"));
    setResult({ kind: "advance", message: r.message, data: r.data });
    return r;
  });
  const late = useAct(async () => {
    const r = unwrap(await api.POST("/sim/customer-late"));
    setResult({ kind: "late", message: r.message, data: r.data });
    return r;
  });
  const bad = useAct(async () => {
    const r = unwrap(await api.POST("/sim/malicious-invoice"));
    setResult({ kind: "malicious", message: r.message, data: r.data });
    const pid = r.data.proposal_id as string | undefined;
    if (pid && r.data.verdict === "ESCALATE") {
      onOpenChange(false);
      setTimeout(() => openApproval(pid), 250);
    }
    return r;
  });
  const reset = useAct(async () => {
    const r = unwrap(await api.POST("/sim/reset"));
    setResult(null);
    return r;
  });
  const tamper = useAct(async () => unwrap(await api.POST("/sim/tamper")), { tone: "warn" });
  const busy = advance.isPending || late.isPending || bad.isPending || reset.isPending;

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={t("sim.title")} description={t("sim.sub")}>
      <div className="space-y-4">
        <p className="num flex items-center gap-2 rounded-lg border border-border bg-surface p-3 text-sm">
          <Clock aria-hidden className="size-4 text-accent" /> {t("sim.date")}: <b>{state ? flong(state.today, lang) : "…"}</b>
        </p>

        <Action icon={<CalendarPlus aria-hidden className="size-5" />} title={t("sim.advance")} body={t("sim.advance.body")} busy={advance.isPending} disabled={busy} onClick={() => advance.mutate()} label={t("sim.run")} testId="sim-advance" />
        <Action icon={<Clock aria-hidden className="size-5" />} title={t("sim.late")} body={t("sim.late.body")} busy={late.isPending} disabled={busy} onClick={() => late.mutate()} label={t("sim.run")} testId="sim-late" />
        <Action icon={<Mail aria-hidden className="size-5" />} title={t("sim.bad")} body={t("sim.bad.body")} busy={bad.isPending} disabled={busy} onClick={() => bad.mutate()} label={t("sim.run")} testId="sim-malicious" />

        {result && <ResultPanel r={result} />}

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          <Button variant="secondary" size="sm" disabled={busy} onClick={() => reset.mutate()} data-testid="sim-reset"><RotateCcw aria-hidden className="size-4" />{t("sim.reset")}</Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => tamper.mutate()} data-testid="sim-tamper"><Wrench aria-hidden className="size-4" />{t("sim.tamper")}</Button>
        </div>
        <p className="text-xs text-muted">{t("sim.footnote")}</p>
      </div>
    </Sheet>
  );

  function ResultPanel({ r }: { r: Result }) {
    const d = r.data as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
    return (
      <Card className="rise space-y-3" role="status" data-testid="sim-result">
        <p className="font-semibold">{r.message}</p>
        {r.kind === "late" && d.applied && (
          <dl className="num grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">{t("sim.r.band")}</dt><dd>{rm(d.band_width_before)} → <b>{rm(d.band_width_after)}</b></dd>
            <dt className="text-muted">{t("sim.r.low")}</dt><dd>{rm(d.low_before.p50)} → <b>{rm(d.low_after.p50)}</b></dd>
            <dt className="text-muted">{t("sim.r.chance")}</dt><dd>{pct(d.p_ok_before)} → <b>{pct(d.p_ok_after)}</b></dd>
          </dl>
        )}
        {(r.kind === "late" || r.kind === "advance") && Array.isArray(d.flips) && d.flips.length > 0 && (
          <ul className="space-y-2">
            {(d.flips as Flip[]).map((f, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                <VerdictBadge verdict={f.from as never} /> <span aria-hidden>→</span> <VerdictBadge verdict={f.to as never} />
                <span className="font-medium">{f.payee}</span>
                {f.release_to && f.to === "HOLD" && <span className="num text-muted">{fdate(f.release_to, lang)}</span>}
              </li>
            ))}
          </ul>
        )}
        {r.kind === "advance" && (
          <p className="num text-sm text-muted">{t("sim.r.advance", { from: rm(d.balance_before), to: rm(d.balance_after), paid: d.paid, docs: d.new_documents })}</p>
        )}
        {r.kind === "malicious" && d.proposal_id && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <VerdictBadge verdict={d.verdict} />
              <span className="text-sm">{t("sim.r.moved", { amount: rm(d.money_moved ?? 0) })}</span>
            </div>
            <Button size="sm" variant="secondary" onClick={() => { onOpenChange(false); openApproval(d.proposal_id); }}>{t("sim.r.openCard")}</Button>
          </div>
        )}
      </Card>
    );
  }
}

function Action({ icon, title, body, onClick, busy, disabled, label, testId }: {
  icon: React.ReactNode; title: string; body: string; onClick: () => void; busy: boolean; disabled: boolean; label: string; testId: string;
}) {
  const { t } = useT();
  return (
    <Card className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 gap-3">
        <span className="mt-0.5 text-accent">{icon}</span>
        <div className="min-w-0">
          <h3 className="font-bold">{title}</h3>
          <p className="text-sm text-muted">{body}</p>
        </div>
      </div>
      <Button onClick={onClick} disabled={disabled} data-testid={testId} aria-label={`${label}: ${title}`}>
        {busy ? t("sim.running") : label}
      </Button>
    </Card>
  );
}
export type { Key };
