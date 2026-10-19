"use client";

import { AlertTriangle, CheckCircle2, Clock, Download, MailQuestion, PiggyBank, ShieldAlert, ShieldCheck, Timer, TrendingDown, UserCheck, Wallet } from "lucide-react";
import Link from "next/link";
import { Async } from "@/components/async";
import { DecisionRow } from "@/components/decision-row";
import { ForecastChart } from "@/components/forecast-chart";
import { useOverlays } from "@/components/overlays";
import { BlockSkeleton, CardsSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useT } from "@/i18n";
import { briefUrl } from "@/lib/api";
import { fdate, pct, rm } from "@/lib/format";
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
        const tint = d.status === "ok" ? "var(--allow)" : d.status === "watch" ? "var(--hold)" : "var(--deny)";
        return (
          <>
            <ScreenHeader title={t("today.title")} answer={t("today.strap", { min: rm(d.min_balance) })}>
              <Button asChild variant="secondary" size="sm">
                <a href={briefUrl} target="_blank" rel="noreferrer"><Download aria-hidden className="size-4" />{t("today.brief")}</a>
              </Button>
            </ScreenHeader>

            <Card className="mb-4 flex items-start gap-4 p-6" data-testid="headline" style={{ backgroundImage: `linear-gradient(115deg, color-mix(in oklab, ${tint} 16%, transparent), transparent 60%)` }}>
              <StatusIcon aria-hidden className={cn("mt-1 size-8 shrink-0", tone)} />
              <div className="min-w-0">
                <p className={cn("text-sm font-bold uppercase tracking-wide", tone)}>{t(`today.status.${d.status}`)}</p>
                <p className="mt-1 text-lg font-medium leading-snug md:text-xl">{txt(d.headline)}</p>
              </div>
            </Card>

            <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Metric icon={Wallet} label={t("today.cash")} value={rm(d.cash_now)} sub={t("today.cash.sub", { reserve: rm(d.reserve) })} hero />
              <Metric icon={ShieldCheck} label={t("today.buffer")} value={t("today.days", { n: Math.round(d.buffer_days) })} sub={t("today.buffer.sub", { min: rm(d.min_balance) })} />
              <Metric icon={Timer} label={t("today.runway")} value={t("today.days", { n: Math.round(d.runway_days) })} sub={t("today.runway.sub", { burn: rm(d.daily_burn) })} />
              <Metric
                icon={TrendingDown} label={t("today.low")} value={rm(d.low_point.worst)} danger={d.low_point.worst < d.min_balance}
                sub={t("today.low.sub", { date: fdate(d.low_point.worst_date, lang), expected: rm(d.low_point.p50) })}
              />
            </div>

            <section aria-labelledby="needs" className="mb-6">
              <h2 id="needs" className="mb-3 text-lg font-bold">{t("today.needs")}</h2>
              {d.needs_you.length === 0 ? (
                <EmptyState title={t("today.needs.none")} body={t("today.needs.none.body")} />
              ) : (
                <ul className="grid gap-3 md:grid-cols-3">
                  {d.needs_you.map((n, i) => {
                    const Icon = KIND_ICON[n.kind];
                    return (
                      <li key={i}>
                        <Card className="flex h-full flex-col gap-3">
                          <div className="flex items-start gap-3">
                            <Icon aria-hidden className={cn("mt-0.5 size-5 shrink-0", n.kind === "approve" ? "text-escalate" : n.kind === "alert" ? "text-deny" : "text-hold")} />
                            <div className="min-w-0">
                              <p className="font-semibold leading-snug">{txt(n.title)}</p>
                              <p className="mt-1 line-clamp-3 text-sm text-muted">{txt(n.detail)}</p>
                            </div>
                          </div>
                          <div className="mt-auto">
                            {n.kind === "approve" && n.proposal_id ? (
                              <Button size="sm" onClick={() => openApproval(n.proposal_id!)} data-testid="review-approval">{t("today.review")}</Button>
                            ) : n.kind === "hold" && n.proposal_id ? (
                              <Button size="sm" variant="secondary" onClick={() => openDecision(n.proposal_id!)}>{t("row.seeWorking")}</Button>
                            ) : (
                              <Button size="sm" variant="secondary" asChild><Link href={n.href}>{t("today.open")}</Link></Button>
                            )}
                          </div>
                        </Card>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section aria-labelledby="mini" className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="mini" className="text-lg font-bold">{t("today.next90")}</h2>
                <Link href="/forecast" className="inline-flex min-h-11 items-center text-sm font-semibold text-accent">{t("today.openForecast")}</Link>
              </div>
              <Async q={f} skeleton={<BlockSkeleton h={200} />}>
                {(fd) => (
                  <Card className="p-2 md:p-4">
                    <ForecastChart data={fd} view="unmanaged" height={220} compact />
                    <p className="num px-2 pb-1 text-xs text-muted">{t("today.mini.note", { p: pct(1 - d.low_point.chance_below_min), min: rm(d.min_balance) })}</p>
                  </Card>
                )}
              </Async>
            </section>

            <section aria-labelledby="week">
              <h2 id="week" className="mb-3 text-lg font-bold">{t("today.week")}</h2>
              {d.week_decisions.length === 0 ? (
                <EmptyState title={t("today.week.none")} />
              ) : (
                <ul className="grid gap-3 md:grid-cols-2" data-testid="week-decisions">
                  {d.week_decisions.map((r) => <DecisionRow key={r.proposal_id} row={r} onOpen={() => openDecision(r.proposal_id)} />)}
                </ul>
              )}
            </section>
          </>
        );
      }}
    </Async>
  );
}

function Metric({ icon: Icon, label, value, sub, hero, danger }: { icon: typeof Wallet; label: string; value: string; sub: string; hero?: boolean; danger?: boolean }) {
  return (
    <Card className="min-w-0">
      <div className="flex items-center gap-2">
        <span aria-hidden className="grid size-8 place-items-center rounded-lg bg-accent/10 text-accent"><Icon className="size-4" /></span>
        <p className="text-sm font-medium text-muted">{label}</p>
      </div>
      <p className={cn("num mt-3 font-bold tracking-tight", hero ? "text-grad text-3xl md:text-4xl" : "text-2xl md:text-3xl", danger && "text-deny")}>{value}</p>
      <p className="mt-1 text-xs text-muted">{sub}</p>
    </Card>
  );
}
