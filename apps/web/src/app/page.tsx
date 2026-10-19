"use client";

import { AlertTriangle, CheckCircle2, ChevronRight, Clock, Download, MailQuestion, PiggyBank, ShieldAlert, UserCheck } from "lucide-react";
import Link from "next/link";
import { Async } from "@/components/async";
import { DecisionList, DecisionRow } from "@/components/decision-row";
import { ForecastChart } from "@/components/forecast-chart";
import { useOverlays } from "@/components/overlays";
import { BlockSkeleton, CardsSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useT } from "@/i18n";
import { briefUrl } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { useForecast, useToday } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const KIND_ICON = { approve: UserCheck, hold: Clock, chase: MailQuestion, alert: ShieldAlert, top_up: PiggyBank } as const;

export default function TodayPage() {
  const { t, lang, txt } = useT();
  const q = useToday();
  const f = useForecast();
  const { openDecision, openApproval } = useOverlays();

  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("today.title")} answer={t("today.question")} /><CardsSkeleton n={4} /></>}>
      {(d) => {
        const StatusIcon = d.status === "ok" ? CheckCircle2 : d.status === "watch" ? Clock : AlertTriangle;
        const tone = d.status === "ok" ? "text-allow" : d.status === "watch" ? "text-hold" : "text-deny";
        const bar = d.status === "ok" ? "border-l-allow" : d.status === "watch" ? "border-l-hold" : "border-l-deny";
        return (
          <>
            <ScreenHeader title={t("today.title")} answer={t("today.strap", { min: rm(d.min_balance) })}>
              <Button asChild variant="secondary" size="sm">
                <a href={briefUrl} target="_blank" rel="noreferrer"><Download aria-hidden className="size-4" />{t("today.brief")}</a>
              </Button>
            </ScreenHeader>

            <Card className="mb-4 overflow-hidden p-0">
              <dl className="grid grid-cols-2 divide-x divide-y divide-border lg:grid-cols-4 lg:divide-y-0">
                <Kpi label={t("today.cash")} value={rm(d.cash_now)} sub={t("today.cash.sub", { reserve: rm(d.reserve) })} big />
                <Kpi label={t("today.buffer")} value={t("today.days", { n: Math.round(d.buffer_days) })} sub={t("today.buffer.sub", { min: rm(d.min_balance) })} />
                <Kpi label={t("today.runway")} value={t("today.days", { n: Math.round(d.runway_days) })} sub={t("today.runway.sub", { burn: rm(d.daily_burn) })} />
                <Kpi
                  label={t("today.low")} value={rm(d.low_point.worst)} danger={d.low_point.worst < d.min_balance}
                  sub={t("today.low.sub", { date: fdate(d.low_point.worst_date, lang), expected: rm(d.low_point.p50) })}
                />
              </dl>
            </Card>

            <Card className={cn("mb-6 flex items-start gap-3 border-l-4 p-4", bar)} data-testid="headline">
              <StatusIcon aria-hidden className={cn("mt-0.5 size-5 shrink-0", tone)} />
              <div className="min-w-0">
                <p className="text-[15px] leading-relaxed"><span className={cn("font-semibold", tone)}>{t(`today.status.${d.status}`)}.</span> {txt(d.headline)}</p>
              </div>
            </Card>

            <div className="mb-8 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
              <Card className="p-4 md:p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">{t("today.next90")}</h2>
                  <Link href="/forecast" className="inline-flex min-h-11 items-center text-[13px] font-medium text-accent md:min-h-8">{t("today.openForecast")}</Link>
                </div>
                <Async q={f} skeleton={<BlockSkeleton h={250} />}>
                  {(fd) => (
                    <>
                      <ForecastChart data={fd} view="unmanaged" height={330} compact />
                    </>
                  )}
                </Async>
              </Card>

              <section aria-labelledby="needs">
                <h2 id="needs" className="mb-2 text-sm font-semibold">{t("today.needs")}</h2>
                {d.needs_you.length === 0 ? (
                  <EmptyState title={t("today.needs.none")} body={t("today.needs.none.body")} />
                ) : (
                  <Card className="overflow-hidden p-0">
                    <ul className="divide-y divide-border">
                      {d.needs_you.map((n, i) => {
                        const Icon = KIND_ICON[n.kind];
                        const go = () => (n.kind === "approve" && n.proposal_id ? openApproval(n.proposal_id) : n.kind === "hold" && n.proposal_id ? openDecision(n.proposal_id) : null);
                        const inner = (
                          <>
                            <Icon aria-hidden className={cn("mt-0.5 size-4 shrink-0", n.kind === "approve" ? "text-escalate" : n.kind === "alert" ? "text-deny" : "text-hold")} />
                            <span className="min-w-0 flex-1">
                              <span className="block text-sm font-medium leading-snug">{txt(n.title)}</span>
                            </span>
                            {n.kind === "approve" ? <span className="shrink-0 self-center rounded-md bg-accent-solid px-2.5 py-1 text-xs font-medium text-on-accent" data-testid="review-approval">{t("today.review")}</span> : <ChevronRight aria-hidden className="size-4 shrink-0 self-center text-muted" />}
                          </>
                        );
                        return (
                          <li key={i}>
                            {n.proposal_id && (n.kind === "approve" || n.kind === "hold") ? (
                              <button onClick={go} className="flex min-h-11 w-full cursor-pointer items-start gap-3 px-4 py-3 text-left hover:bg-subtle">{inner}</button>
                            ) : (
                              <Link href={n.href} className="flex min-h-11 items-start gap-3 px-4 py-3 hover:bg-subtle">{inner}</Link>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </Card>
                )}
              </section>
            </div>

            <section aria-labelledby="week">
              <h2 id="week" className="mb-2 text-sm font-semibold">{t("today.week")}</h2>
              {d.week_decisions.length === 0 ? (
                <EmptyState title={t("today.week.none")} />
              ) : (
                <div data-testid="week-decisions">
                  <DecisionList>
                    {d.week_decisions.map((r) => <DecisionRow key={r.proposal_id} row={r} compact onOpen={() => openDecision(r.proposal_id)} />)}
                  </DecisionList>
                </div>
              )}
            </section>
          </>
        );
      }}
    </Async>
  );
}

function Kpi({ label, value, sub, big, danger }: { label: string; value: string; sub: string; big?: boolean; danger?: boolean }) {
  return (
    <div className="min-w-0 p-5">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="mt-1">
        <span className={cn("num block font-semibold tracking-tight", big ? "text-3xl" : "text-2xl", danger && "text-deny")}>{value}</span>
        <span className="mt-1 block text-xs text-muted">{sub}</span>
      </dd>
    </div>
  );
}
