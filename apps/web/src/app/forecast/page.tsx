"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FlaskConical, Info, TriangleAlert } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { Async } from "@/components/async";
import { FlowChart, FlowLegend, type FlowPoint } from "@/components/flow-chart";
import { ForecastChart, type View } from "@/components/forecast-chart";
import { useOverlays } from "@/components/overlays";
import { BlockSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VerdictBadge } from "@/components/ui/verdict-badge";
import { useT } from "@/i18n";
import { api, unwrap, type Event, type ForecastOut } from "@/lib/api";
import { addDays, daysBetween, fdate, parseDate, pct, rm } from "@/lib/format";
import { useForecast } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export default function ForecastPage() {
  return (
    <Suspense fallback={<BlockSkeleton h={420} />}>
      <ForecastScreen />
    </Suspense>
  );
}

const LATE_DAYS = 20;

function ForecastScreen() {
  const { t, lang } = useT();
  const q = useForecast();
  const params = useSearchParams();
  const [view, setView] = useState<View>("unmanaged");
  const [late, setLate] = useState<string[]>(() => (params.get("late") ?? "").split(",").filter(Boolean).map((x) => x.split(":")[0]));
  const [skip, setSkip] = useState<string[]>([]);
  const base = q.data;
  const active = late.length + skip.length > 0;

  const whatif = useQuery({
    queryKey: ["whatif", late, skip],
    enabled: active && !!base,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      unwrap(await api.POST("/forecast/whatif", { body: { late: late.map((c) => ({ customer_id: c, days: LATE_DAYS })), skip_bill_ids: skip } })),
  });

  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("forecast.title")} answer={t("forecast.question")} /><BlockSkeleton h={420} /></>}>
      {(b) => {
        const data: ForecastOut = active && whatif.data ? whatif.data : b;
        const lowTxt = t("forecast.answer", { low: rm(b.low.worst), date: fdate(b.low.worst_date, lang), min: rm(b.min_balance), chance: pct(1 - b.p_ok_unmanaged) });
        return (
          <>
            <ScreenHeader title={t("forecast.title")} answer={b.p_ok_unmanaged >= b.required ? t("forecast.answer.ok", { min: rm(b.min_balance) }) : lowTxt} />

            <div className="mb-4 flex flex-wrap items-center gap-3">
              <div role="group" aria-label={t("forecast.view")} className="inline-flex rounded-lg border border-border bg-subtle p-0.5">
                {(["unmanaged", "managed"] as const).map((v) => (
                  <button key={v} onClick={() => setView(v)} aria-pressed={view === v} data-testid={`view-${v}`}
                    className={cn("min-h-11 cursor-pointer rounded-md px-3 text-[13px] font-medium md:min-h-8", view === v ? "bg-surface text-text shadow-card" : "text-muted hover:text-text")}>
                    {t(v === "unmanaged" ? "forecast.view.unmanaged" : "forecast.view.managed")}
                  </button>
                ))}
              </div>
              <p className="num text-sm text-muted">
                {view === "unmanaged"
                  ? t("forecast.chance.un", { p: pct(data.p_ok_unmanaged), min: rm(data.min_balance) })
                  : t("forecast.chance.man", { p: pct(data.p_ok_managed), min: rm(data.min_balance) })}
              </p>
            </div>

            {active && whatif.data && <WhatIfDelta data={whatif.data} loading={whatif.isFetching} />}

            <Tabs defaultValue="chart" className="mt-2">
              <TabsList aria-label={t("forecast.tabs")}>
                <TabsTrigger value="chart">{t("forecast.tab.chart")}</TabsTrigger>
                <TabsTrigger value="flow">{t("forecast.tab.flow")}</TabsTrigger>
                <TabsTrigger value="calendar">{t("forecast.tab.calendar")}</TabsTrigger>
                <TabsTrigger value="table">{t("forecast.tab.table")}</TabsTrigger>
              </TabsList>
              <TabsContent value="chart" className="mt-3">
                <Card className="p-2 md:p-4">
                  <ForecastChart data={data} view={view} height={360} />
                  <Legend />
                </Card>
                <WhyDip data={b} />
              </TabsContent>
              <TabsContent value="flow" className="mt-3"><CashFlowTab data={data} view={view} /></TabsContent>
              <TabsContent value="calendar" className="mt-3"><CalendarTab data={data} view={view} /></TabsContent>
              <TabsContent value="table" className="mt-3"><TableTab data={data} view={view} /></TabsContent>
            </Tabs>

            <div className="mt-4"><WhatIf base={b} late={late} skip={skip} setLate={setLate} setSkip={setSkip} /></div>

            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <TrackRecord data={b} />
              <Assumptions data={b} />
            </div>
          </>
        );
      }}
    </Async>
  );
}

function Legend() {
  const { t } = useT();
  return (
    <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 px-2 text-xs text-muted">
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-5 rounded-sm bg-accent/25" />{t("legend.band50")}</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-2.5 w-5 rounded-sm bg-accent/12" />{t("legend.band80")}</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-0.5 w-5 bg-accent" />{t("legend.median")}</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="text-deny">- - -</span>{t("legend.min")}</li>
      <li>▼ {t("legend.bill")}</li>
      <li>▲ {t("legend.invoice")}</li>
    </ul>
  );
}

function WhyDip({ data }: { data: ForecastOut }) {
  const { t, lang } = useT();
  const { bill, invoice } = data.causes;
  if (data.p_ok_unmanaged >= data.required || (!bill && !invoice)) return null;
  return (
    <Card className="mt-4">
      <h2 className="mb-2 text-base font-bold">{t("forecast.why")}</h2>
      <ul className="space-y-2 text-[15px]">
        {bill && (
          <li className="flex gap-2"><span aria-hidden>▼</span>
            <span>{t("forecast.why.bill", { payee: bill.label, amount: rm(-bill.amount), date: fdate(bill.date, lang) })}
              {bill.verdict === "HOLD" && bill.release_on ? " " + t("forecast.why.held", { date: fdate(bill.release_on, lang) }) : ""}</span></li>
        )}
        {invoice && (
          <li className="flex gap-2"><span aria-hidden>▲</span>
            <span>{t("forecast.why.invoice", { customer: invoice.label, amount: rm(invoice.amount), date: fdate(invoice.date, lang) })}</span></li>
        )}
      </ul>
    </Card>
  );
}

function WhatIf({ base, late, skip, setLate, setSkip }: { base: ForecastOut; late: string[]; skip: string[]; setLate: (x: string[]) => void; setSkip: (x: string[]) => void }) {
  const { t } = useT();
  const customers = useMemo(() => {
    const m = new Map<string, { id: string; name: string; amount: number }>();
    for (const e of base.events) if (e.kind === "invoice" && e.customer_id) {
      const cur = m.get(e.customer_id) ?? { id: e.customer_id, name: e.label, amount: 0 };
      cur.amount += e.amount;
      m.set(e.customer_id, cur);
    }
    return [...m.values()].sort((a, b) => b.amount - a.amount).slice(0, 5);
  }, [base.events]);
  const bills = useMemo(
    () => base.events.filter((e) => e.kind === "bill").sort((a, b) => a.amount - b.amount).slice(0, 4),
    [base.events],
  );
  const toggle = (arr: string[], id: string, set: (x: string[]) => void) => set(arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id]);
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <FlaskConical aria-hidden className="size-5 text-accent" />
        <h2 className="text-base font-bold">{t("whatif.title")}</h2>
      </div>
      <p className="mb-3 text-sm text-muted">{t("whatif.sub")}</p>
      <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
        <fieldset>
          <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("whatif.late")}</legend>
          {customers.map((c) => (
            <label key={c.id} className="flex min-h-11 cursor-pointer items-center justify-between gap-3 text-sm">
              <span className="min-w-0"><span className="font-medium">{c.name}</span> <span className="num text-muted">{rm(c.amount)}</span><span className="text-muted"> · {t("whatif.days", { n: LATE_DAYS })}</span></span>
              <Switch checked={late.includes(c.id)} onCheckedChange={() => toggle(late, c.id, setLate)} aria-label={`${c.name} ${t("whatif.days", { n: LATE_DAYS })}`} data-testid={`late-${c.id}`} />
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("whatif.skip")}</legend>
          {bills.map((b) => (
            <label key={b.id} className="flex min-h-11 cursor-pointer items-center justify-between gap-3 text-sm">
              <span className="min-w-0"><span className="font-medium">{b.label}</span> <span className="num text-muted">{rm(-b.amount)}</span></span>
              <Switch checked={skip.includes(b.id)} onCheckedChange={() => toggle(skip, b.id, setSkip)} aria-label={`${t("whatif.skipOne")} ${b.label}`} />
            </label>
          ))}
        </fieldset>
      </div>
      {(late.length > 0 || skip.length > 0) && (
        <Button className="mt-2" variant="ghost" size="sm" onClick={() => { setLate([]); setSkip([]); }}>{t("whatif.clear")}</Button>
      )}
    </Card>
  );
}

function WhatIfDelta({ data, loading }: { data: ForecastOut; loading: boolean }) {
  const { t, lang } = useT();
  const changes = data.changes ?? [];
  const base = data.baseline!;
  return (
    <Card className={cn("rise mb-4 border-accent/50", loading && "opacity-70")} role="status" aria-live="polite">
      <p className="flex items-start gap-2 text-[15px] font-medium"><Info aria-hidden className="mt-0.5 size-4 shrink-0 text-accent" />
        {t("whatif.delta", { before: rm(base.low.worst), after: rm(data.low.worst), n: changes.length })}</p>
      {changes.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {changes.map((c) => (
            <li key={c.proposal_id} className="flex flex-wrap items-center gap-2 text-sm">
              {c.from && <VerdictBadge verdict={c.from as never} />}{c.from && <span aria-hidden>→</span>}<VerdictBadge verdict={c.to as never} />
              <span className="font-medium">{c.payee}</span>{c.release_to && c.to !== "ALLOW" && <span className="num text-muted">{fdate(c.release_to, lang)}</span>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CalendarTab({ data, view }: { data: ForecastOut; view: View }) {
  const { t, lang } = useT();
  const { openDecision } = useOverlays();
  const [sel, setSel] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const months = useMemo(() => {
    const seen: string[] = [];
    for (const d of data.days) { const m = d.slice(0, 7); if (!seen.includes(m)) seen.push(m); }
    return seen;
  }, [data.days]);
  const month = months[Math.min(page, months.length - 1)];
  const first = parseDate(`${month}-01`);
  const lead = (first.getUTCDay() + 6) % 7; // Monday first
  const daysInMonth = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  const byDate = useMemo(() => { const m = new Map<string, Event[]>(); for (const e of data.events) m.set(e.date, [...(m.get(e.date) ?? []), e]); return m; }, [data.events]);
  const releases = useMemo(() => { const m = new Map<string, Event[]>(); for (const e of data.events) if (e.release_on && e.release_on !== e.date) m.set(e.release_on, [...(m.get(e.release_on) ?? []), e]); return m; }, [data.events]);
  const band = data[view];
  const dow = lang === "ms" ? ["Isn", "Sel", "Rab", "Kha", "Jum", "Sab", "Ahd"] : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const cells: (string | null)[] = [...Array(lead).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`)];
  const selEvents = sel ? [...(byDate.get(sel) ?? []), ...(releases.get(sel) ?? []).map((e) => ({ ...e, __release: true }))] : [];

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <Button variant="ghost" size="icon" aria-label={t("calendar.prev")} disabled={page === 0} onClick={() => setPage(page - 1)}><ChevronLeft aria-hidden className="size-5" /></Button>
        <h2 className="text-base font-bold">{first.toLocaleDateString(lang === "ms" ? "ms-MY" : "en-GB", { month: "long", year: "numeric", timeZone: "UTC" })}</h2>
        <Button variant="ghost" size="icon" aria-label={t("calendar.next")} disabled={page >= months.length - 1} onClick={() => setPage(page + 1)}><ChevronRight aria-hidden className="size-5" /></Button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-muted">{dow.map((d) => <div key={d}>{d}</div>)}</div>
      <div className="mt-1 grid grid-cols-7 gap-1">
        {cells.map((d, i) => {
          if (!d) return <div key={`b${i}`} />;
          const idx = data.days.indexOf(d);
          const ev = byDate.get(d) ?? [];
          const rel = releases.get(d) ?? [];
          const low = idx >= 0 && band.p10[idx] < data.min_balance;
          return (
            <button key={d} onClick={() => setSel(d)} disabled={idx < 0}
              aria-label={`${fdate(d, lang)}${low ? ", " + t("calendar.lowDay") : ""}${ev.length ? ", " + ev.map((e) => e.label).join(", ") : ""}`}
              className={cn("flex min-h-14 cursor-pointer flex-col items-center justify-start gap-0.5 rounded-lg border p-1 text-xs disabled:cursor-default disabled:opacity-40",
                sel === d ? "border-accent bg-accent/10" : "border-border bg-surface hover:border-accent/50", low && "ring-1 ring-inset ring-deny/50")}>
              <span className="num font-semibold">{parseDate(d).getUTCDate()}</span>
              <span className="flex flex-wrap justify-center gap-0.5 leading-none">
                {ev.slice(0, 3).map((e) => <span key={e.id} aria-hidden className={cn("text-[11px]", e.kind === "invoice" ? "text-accent" : e.verdict === "HOLD" ? "text-hold" : e.verdict === "ESCALATE" ? "text-escalate" : e.verdict === "DENY" ? "text-deny" : "text-allow")}>{e.kind === "invoice" ? "▲" : e.verdict === "HOLD" ? "◷" : e.verdict === "ESCALATE" ? "◉" : e.verdict === "DENY" ? "✕" : "▼"}</span>)}
                {rel.length > 0 && <span aria-hidden className="text-[11px] text-hold">⏵</span>}
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-muted">{t("calendar.legend")}</p>
      {sel && (
        <div className="rise mt-3 rounded-lg border border-border p-3" aria-live="polite">
          <p className="mb-2 font-semibold">{fdate(sel, lang)}{data.days.indexOf(sel) >= 0 && <span className="num font-normal text-muted"> · {t("chart.balance")} {rm(band.p50[data.days.indexOf(sel)])}</span>}</p>
          {selEvents.length === 0 ? <p className="text-sm text-muted">{t("calendar.nothing")}</p> : (
            <ul className="space-y-2">
              {selEvents.map((e, i) => (
                <li key={`${e.id}-${i}`} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="flex min-w-0 items-center gap-2">
                    {e.kind === "invoice" ? <span aria-hidden>▲</span> : <span aria-hidden>▼</span>}
                    <span className="truncate font-medium">{e.label}</span>
                    {"__release" in e && <span className="text-xs text-muted">{t("calendar.releasesToday")}</span>}
                  </span>
                  <span className="flex items-center gap-2"><span className="num">{rm(e.amount)}</span>{e.verdict && <VerdictBadge verdict={e.verdict} />}
                    {e.proposal_id && <Button size="sm" variant="ghost" onClick={() => openDecision(e.proposal_id!)}>{t("row.seeWorking")}</Button>}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}

function TableTab({ data, view }: { data: ForecastOut; view: View }) {
  const { t, lang } = useT();
  const { openDecision } = useOverlays();
  const band = data[view];
  const rows = data.events.filter((e) => e.kind !== "statutory" || true);
  if (rows.length === 0) return <EmptyState title={t("table.none")} />;
  return (
    <Card className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">{t("forecast.tab.table")}</caption>
          <thead className="border-b border-border bg-bg text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-4 py-2">{t("table.date")}</th><th scope="col" className="px-4 py-2">{t("table.what")}</th>
              <th scope="col" className="px-4 py-2 text-right">{t("table.amount")}</th><th scope="col" className="px-4 py-2">{t("table.helm")}</th>
              <th scope="col" className="px-4 py-2 text-right">{t("table.balance")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => {
              const i = data.days.indexOf(e.date);
              return (
                <tr key={e.id} className="border-b border-border last:border-0">
                  <td className="num whitespace-nowrap px-4 py-2">{fdate(e.date, lang)}</td>
                  <td className="px-4 py-2"><span aria-hidden>{e.kind === "invoice" ? "▲ " : "▼ "}</span>{e.label}<span className="sr-only"> ({e.kind})</span></td>
                  <td className={cn("num px-4 py-2 text-right", e.amount < 0 ? "" : "text-allow")}>{rm(e.amount)}</td>
                  <td className="px-4 py-2">
                    {e.verdict ? (
                      <button onClick={() => e.proposal_id && openDecision(e.proposal_id)} className="inline-flex min-h-9 cursor-pointer items-center gap-2">
                        <VerdictBadge verdict={e.verdict} />{e.release_on && e.release_on !== e.date && <span className="num text-xs text-muted">{fdate(e.release_on, lang)}</span>}
                      </button>
                    ) : <span className="text-muted">—</span>}
                  </td>
                  <td className={cn("num px-4 py-2 text-right", i >= 0 && band.p50[i] < data.min_balance && "font-semibold text-deny")}>{i >= 0 ? rm(band.p50[i]) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function TrackRecord({ data }: { data: ForecastOut }) {
  const { t, lang } = useT();
  const tr = data.track_record;
  return (
    <Card>
      <h2 className="mb-1 text-base font-bold">{t("track.title")}</h2>
      {tr.coverage_80 === null ? <p className="text-sm text-muted">{t("track.none")}</p> : (
        <>
          <p className="text-[15px]">{t("track.body", { cov: pct(tr.coverage_80), stated: pct(tr.stated_coverage), n: tr.days_checked, err: rm(tr.median_abs_error) })}</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <caption className="sr-only">{t("track.title")}</caption>
              <thead className="text-muted"><tr><th scope="col" className="py-1 pr-3">{t("track.from")}</th><th scope="col" className="py-1 pr-3">{t("track.days")}</th><th scope="col" className="py-1 pr-3">{t("track.inside")}</th><th scope="col" className="py-1">{t("track.error")}</th></tr></thead>
              <tbody className="num">{tr.snapshots.map((s) => <tr key={s.origin} className="border-t border-border"><td className="py-1 pr-3">{fdate(s.origin, lang)}</td><td className="pr-3">{s.days_checked}</td><td className="pr-3">{pct(s.inside_80)}</td><td>{rm(s.median_abs_error)}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted">{t("track.note")}</p>
        </>
      )}
    </Card>
  );
}

function Assumptions({ data }: { data: ForecastOut }) {
  const { t } = useT();
  const a = data.assumptions as { paths?: number; history_invoices_used?: number; customers_learned?: number };
  return (
    <Card>
      <h2 className="mb-2 flex items-center gap-2 text-base font-bold"><TriangleAlert aria-hidden className="size-4 text-hold" />{t("assume.title")}</h2>
      <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted">
        <li>{t("assume.method", { paths: a.paths ?? 0, n: a.history_invoices_used ?? 0, c: a.customers_learned ?? 0 })}</li>
        <li>{t("assume.band")}</li>
        <li>{t("assume.statutory")}</li>
        <li>{t("assume.synthetic")}</li>
      </ul>
    </Card>
  );
}
export { addDays, daysBetween };


function CashFlowTab({ data, view }: { data: ForecastOut; view: View }) {
  const { t, lang } = useT();
  const { openDecision } = useOverlays();
  const [sel, setSel] = useState<string | null>(null);
  // Known invoices and bills only, in weeks from today. With Helm, held bills sit on their release date.
  const items = useMemo(
    () => data.events.map((e) => ({ ...e, on: view === "managed" && e.release_on ? e.release_on : e.date })),
    [data.events, view],
  );
  const weeks = useMemo<FlowPoint[]>(() => {
    const n = Math.ceil((data.days.length - 1) / 7);
    const out: FlowPoint[] = Array.from({ length: n }, (_, w) => ({ key: String(w), label: fdate(addDays(data.today, w * 7), lang), money_in: 0, money_out: 0 }));
    for (const e of items) {
      const w = Math.floor(daysBetween(data.today, e.on) / 7);
      if (w < 0 || w >= n) continue;
      if (e.amount > 0) out[w].money_in += e.amount; else out[w].money_out += -e.amount;
    }
    return out;
  }, [items, data.today, data.days.length, lang]);
  const picked = sel === null ? [] : items.filter((e) => Math.floor(daysBetween(data.today, e.on) / 7) === Number(sel)).sort((a, b) => a.on.localeCompare(b.on));
  const byType = useMemo(() => {
    const m: Record<string, number> = { payroll: 0, statutory: 0, bill: 0 };
    for (const e of items) if (e.amount < 0) m[e.kind] = (m[e.kind] ?? 0) - e.amount;
    return m;
  }, [items]);
  const maxType = Math.max(...Object.values(byType), 1);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <Card className="p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">{t("flow.title")}</h2>
          <p className="text-xs text-muted">{t("flow.note")}</p>
        </div>
        <FlowChart data={weeks} height={280} selected={sel} onSelect={(k) => setSel(sel === k ? null : k)} ariaLabel={t("flow.aria")} />
        <FlowLegend />
        <p className="mt-2 text-xs text-muted">{sel === null ? t("flow.hint") : ""}</p>
        {sel !== null && (
          <div className="rise mt-3 rounded-lg border border-border" aria-live="polite">
            <p className="border-b border-border px-3 py-2 text-[13px] font-semibold">{t("flow.week", { date: weeks[Number(sel)].label })}</p>
            <ul className="divide-y divide-border">
              {picked.length === 0 && <li className="px-3 py-3 text-[13px] text-muted">{t("calendar.nothing")}</li>}
              {picked.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 px-3 py-2 text-[13px]">
                  <span className="flex min-w-0 items-center gap-2">
                    <span aria-hidden>{e.amount > 0 ? "▲" : "▼"}</span>
                    <span className="truncate font-medium">{e.label}</span>
                    <span className="shrink-0 rounded bg-subtle px-1.5 py-0.5 text-[11px] text-muted">{e.kind === "invoice" ? t("flow.expected") : t("flow.due")} {fdate(e.on, lang)}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className={cn("num font-semibold", e.amount > 0 && "text-allow")}>{rm(e.amount)}</span>
                    {e.proposal_id && <Button size="sm" variant="ghost" onClick={() => openDecision(e.proposal_id!)}>{t("row.seeWorking")}</Button>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <Card className="p-4 md:p-5">
        <h2 className="mb-3 text-sm font-semibold">{t("flow.byType")}</h2>
        <ul className="space-y-3">
          {(["payroll", "statutory", "bill"] as const).map((k) => (
            <li key={k}>
              <div className="mb-1 flex justify-between text-[13px]"><span>{t(`flow.type.${k}` as never)}</span><span className="num font-semibold">{rm(byType[k])}</span></div>
              <div className="h-2 overflow-hidden rounded-full bg-subtle"><div className="h-full rounded-full" style={{ width: `${(byType[k] / maxType) * 100}%`, background: "var(--chart-line)" }} /></div>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-xs text-muted">{t("flow.byType.note")}</p>
      </Card>
    </div>
  );
}
