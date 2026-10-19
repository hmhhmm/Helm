"use client";

import { ArrowDownToLine, ArrowUpFromLine, Info } from "lucide-react";
import { Async } from "@/components/async";
import { FlowChart, FlowLegend } from "@/components/flow-chart";
import { useOverlays } from "@/components/overlays";
import { CardsSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { VerdictBadge } from "@/components/ui/verdict-badge";
import { useT } from "@/i18n";
import { api, unwrap } from "@/lib/api";
import { fdate, fmonth, pct, rm } from "@/lib/format";
import { useAct, useCash } from "@/lib/hooks";

export default function CashPage() {
  const { t, lang, txt } = useT();
  const q = useCash();
  const { openApproval } = useOverlays();
  const run = useAct(async (id: string) => unwrap(await api.POST("/cash/{proposal_id}/execute", { params: { path: { proposal_id: id } } })));
  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("cash.title")} answer={t("cash.question")} /><CardsSkeleton n={2} /></>}>
      {(d) => {
        const max = Math.max(d.operating * 1.15, d.comfort * 1.6, 1);
        const pctOf = (v: number) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
        const total = d.operating + d.reserve;
        return (
          <>
            <ScreenHeader title={t("cash.title")} answer={txt(d.summary)} />
            <div className="mb-6 grid gap-4 md:grid-cols-2">
              <Card>
                <h2 className="text-sm font-medium text-muted">{t("cash.operating")}</h2>
                <p className="num mt-1 text-3xl font-bold">{rm(d.operating)}</p>
                <div className="relative mt-4 h-4 overflow-hidden rounded-full border border-border bg-bg" role="img"
                  aria-label={t("cash.band.aria", { cash: rm(d.operating), min: rm(d.min_balance), comfort: rm(d.comfort) })}>
                  <div className="absolute inset-y-0 left-0 bg-deny/25" style={{ width: pctOf(d.min_balance) }} />
                  <div className="absolute inset-y-0 bg-hold/25" style={{ left: pctOf(d.min_balance), width: `calc(${pctOf(d.comfort)} - ${pctOf(d.min_balance)})` }} />
                  <div className="absolute inset-y-0 bg-allow/20" style={{ left: pctOf(d.comfort), right: 0 }} />
                  <div className="absolute inset-y-0 w-1 rounded bg-text" style={{ left: `calc(${pctOf(d.operating)} - 2px)` }} />
                </div>
                <ul className="mt-2 grid grid-cols-3 gap-2 text-[11px] text-muted">
                  <li><span aria-hidden className="mr-1 inline-block size-2 rounded-sm bg-deny/50" />{t("cash.zone.below", { min: rm(d.min_balance) })}</li>
                  <li><span aria-hidden className="mr-1 inline-block size-2 rounded-sm bg-hold/50" />{t("cash.zone.cushion", { comfort: rm(d.comfort) })}</li>
                  <li><span aria-hidden className="mr-1 inline-block size-2 rounded-sm bg-allow/40" />{t("cash.zone.spare")}</li>
                </ul>
              </Card>
              <Card>
                <h2 className="text-sm font-medium text-muted">{t("cash.reserve")}</h2>
                <p className="num mt-1 text-3xl font-bold">{rm(d.reserve)}</p>
                <p className="num mt-2 text-sm text-muted">{t("cash.split", { op: pct(d.operating / total), re: pct(d.reserve / total) })}</p>
                <p className="mt-2 flex items-start gap-1.5 text-xs text-muted"><Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />{t("cash.estimate", { apy: (d.apy * 100).toFixed(1) })}</p>
              </Card>
            </div>

            <Card className="mb-6 p-4 md:p-5">
              <h2 className="text-sm font-semibold">{t("cash.history")}</h2>
              <p className="mb-3 text-xs text-muted">{t("cash.history.sub")}</p>
              <FlowChart data={d.history.map((h) => ({ key: h.month, label: fmonth(h.month, lang), money_in: h.money_in, money_out: h.money_out }))} height={230} ariaLabel={t("cash.history")} />
              <FlowLegend />
            </Card>

            <h2 className="mb-3 text-base font-semibold">{t("cash.suggestions")}</h2>
            {d.ideas.length === 0 ? <EmptyState title={t("cash.none")} body={t("cash.none.body")} /> : (
              <ul className="space-y-3" data-testid="cash-ideas">
                {d.ideas.map((i) => {
                  const Icon = i.kind === "sweep" ? ArrowDownToLine : ArrowUpFromLine;
                  return (
                    <li key={i.proposal_id}>
                      <Card className="space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex items-start gap-3">
                            <Icon aria-hidden className="mt-0.5 size-5 text-accent" />
                            <div>
                              <h3 className="font-bold">{i.kind === "sweep" ? t("cash.sweep", { amount: rm(i.amount) }) : t("cash.topup", { amount: rm(i.amount) })}</h3>
                              <p className="num text-sm text-muted">{t("cash.on", { date: fdate(i.on, lang) })}</p>
                            </div>
                          </div>
                          <VerdictBadge verdict={i.verdict} />
                        </div>
                        <p className="text-[15px]">{lang === "ms" ? i.reason_ms : i.reason}</p>
                                                {i.interest_estimate != null && (
                          <p className="num text-sm"><b>{t("cash.interest", { rm: rm(i.interest_estimate) })}</b> <span className="text-muted">{t("cash.interest.note")}</span></p>
                        )}
                        <div className="flex flex-wrap gap-2">
                          {i.verdict === "ALLOW" && <Button onClick={() => run.mutate(i.proposal_id)} disabled={run.isPending} data-testid={`do-${i.kind}`}>{t("cash.do")}</Button>}
                          {i.verdict === "ESCALATE" && <Button variant="secondary" onClick={() => openApproval(i.proposal_id)}>{t("today.review")}</Button>}
                        </div>
                      </Card>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        );
      }}
    </Async>
  );
}
