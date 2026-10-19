"use client";

import { Copy, Mail } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Async } from "@/components/async";
import { BlockSkeleton, CardsSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useT, type Key } from "@/i18n";
import { api, unwrap, type Schemas } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { useAct, useCollections } from "@/lib/hooks";
import { cn } from "@/lib/utils";

type Idea = Schemas["Idea"];

const BUCKET = { not_due: "var(--chart-line)", d1_30: "var(--hold)", d31_60: "var(--deny)", d60: "var(--text)" } as const;

export default function CollectionsPage() {
  const { t, lang, txt } = useT();
  const q = useCollections();
  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("collections.title")} answer={t("collections.question")} /><CardsSkeleton n={3} /></>}>
      {(d) => (
        <>
          <ScreenHeader title={t("collections.title")} answer={txt(d.summary)} />
          <section aria-labelledby="rank" className="mb-8">
            <h2 id="rank" className="mb-0.5 text-base font-semibold">{t("collections.rank")}</h2>
            <p className="mb-3 text-[13px] text-muted">{t("collections.rank.sub", { days: d.assumption_days })}</p>
            {d.ideas.length === 0 ? <EmptyState title={t("collections.none")} /> : (
              <Card className="overflow-hidden p-0">
                <div className="hidden grid-cols-[auto_minmax(0,1.4fr)_120px_150px_auto_auto] gap-x-4 border-b border-border px-4 py-2 text-xs text-muted md:grid" aria-hidden>
                  <span className="w-6" /><span>{t("collections.col.customer")}</span><span>{t("collections.open")}</span><span>{t("collections.col.lifts")}</span><span className="w-[104px]">{t("collections.tone")}</span><span className="w-[92px]" />
                </div>
                <ol className="divide-y divide-border" data-testid="chase-ranking">{d.ideas.slice(0, 8).map((i) => <IdeaCard key={i.customer_id} idea={i} />)}</ol>
              </Card>
            )}
          </section>

          <section aria-labelledby="age" className="mb-8">
            <h2 id="age" className="mb-3 text-base font-semibold">{t("collections.ageing")}</h2>
            <Card className="mb-3 p-4">
              <h3 className="mb-2 text-[13px] font-semibold">{t("collections.statusbar")}</h3>
              <div className="flex h-3 overflow-hidden rounded-full bg-subtle" role="img" aria-label={t("collections.statusbar")}>
                {(["not_due", "d1_30", "d31_60", "d60"] as const).map((k) => {
                  const tot = d.ageing[k].reduce((x, y) => x + y.amount, 0);
                  return tot > 0 ? <div key={k} style={{ width: `${(tot / d.total_open) * 100}%`, background: BUCKET[k] }} className="border-r border-surface last:border-0" /> : null;
                })}
              </div>
              <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
                {(["not_due", "d1_30", "d31_60", "d60"] as const).map((k) => (
                  <li key={k} className="flex items-center gap-1.5"><span aria-hidden className="size-2.5 rounded-sm" style={{ background: BUCKET[k] }} />{t(`age.${k}` as Key)} <span className="num font-medium text-text">{rm(d.ageing[k].reduce((x, y) => x + y.amount, 0))}</span></li>
                ))}
              </ul>
            </Card>
            <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
              {(["not_due", "d1_30", "d31_60", "d60"] as const).map((k) => {
                const list = d.ageing[k];
                const total = list.reduce((x, y) => x + y.amount, 0);
                return (
                  <Card key={k} className="p-4">
                    <p className="text-[13px] text-muted">{t(`age.${k}` as Key)}</p>
                    <p className={cn("num mt-1 text-xl font-semibold", k !== "not_due" && total > 0 && "text-hold")}>{rm(total)}</p>
                    <p className="num text-xs text-muted">{t("collections.count", { n: list.length })}</p>
                  </Card>
                );
              })}
            </div>
            <Card className="overflow-hidden p-0">
              <div className="max-h-[26rem] overflow-auto" tabIndex={0} aria-label={t("collections.ageing")}>
                <table className="w-full min-w-[560px] text-left text-sm">
                  <caption className="sr-only">{t("collections.ageing")}</caption>
                  <thead className="sticky top-0 border-b border-border bg-surface text-xs text-muted">
                    <tr><th scope="col" className="px-4 py-2 font-medium">{t("collections.col.customer")}</th><th scope="col" className="px-4 py-2 font-medium">{t("collections.col.invoice")}</th><th scope="col" className="px-4 py-2 font-medium">{t("collections.col.status")}</th><th scope="col" className="px-4 py-2 text-right font-medium">{t("table.amount")}</th></tr>
                  </thead>
                  <tbody className="num">
                    {(["d60", "d31_60", "d1_30", "not_due"] as const).flatMap((k) => d.ageing[k]).map((inv) => (
                      <tr key={inv.id} className="border-b border-border last:border-0">
                        <td className="px-4 py-2 font-sans font-medium">{inv.customer}{inv.chased_on && <span className="ml-2 text-xs font-normal text-allow">{t("collections.chased", { date: fdate(inv.chased_on, lang) })}</span>}{inv.late_signal_days > 0 && <span className="ml-2 text-xs font-normal text-hold">{t("collections.signal", { n: inv.late_signal_days })}</span>}</td>
                        <td className="px-4 py-2 text-muted">{inv.number}</td>
                        <td className={cn("px-4 py-2", inv.days_overdue > 0 ? "text-hold" : "text-muted")}>{inv.days_overdue > 0 ? t("collections.late", { n: inv.days_overdue }) : t("decision.due", { date: fdate(inv.due, lang) })}</td>
                        <td className="px-4 py-2 text-right font-semibold">{rm(inv.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>

          <section aria-labelledby="dso">
            <h2 id="dso" className="mb-0.5 text-base font-semibold">{t("collections.dso")}</h2>
            <p className="mb-3 text-sm text-muted">{d.dso.current ? t("collections.dso.now", { n: Math.round(d.dso.current) }) : ""} {t("collections.dso.sub")}</p>
            <Card className="p-2 md:p-4">
              {d.dso.series.length < 2 ? <BlockSkeleton h={120} /> : (
                <div role="img" aria-label={t("collections.dso.aria", { n: Math.round(d.dso.current ?? 0) })} className="h-52 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={d.dso.series} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid stroke="var(--border)" vertical={false} />
                      <XAxis dataKey="month" stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }} />
                      <YAxis width={36} stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }} domain={[(min: number) => Math.floor(min - 5), (max: number) => Math.ceil(max + 5)]} allowDecimals={false} />
                      <Tooltip formatter={(v) => [`${v} ${t("collections.days")}`, "DSO"]} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8 }} />
                      <Line dataKey="dso" stroke="var(--accent)" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </section>
        </>
      )}
    </Async>
  );
}

function IdeaCard({ idea }: { idea: Idea }) {
  const { t, lang } = useT();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const tone = useAct(async (tone: "friendly" | "firm") => { unwrap(await api.PUT("/collections/{customer_id}/tone", { params: { path: { customer_id: idea.customer_id } }, body: { tone } })); });
  const chase = useAct(async () => unwrap(await api.POST("/collections/{customer_id}/chase", { params: { path: { customer_id: idea.customer_id } } })));
  const text = (l: "en" | "ms") => (l === "ms" ? idea.draft_ms : idea.draft_en);
  return (
    <li className="px-4 py-3">
      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-x-4 gap-y-2 md:grid-cols-[auto_minmax(0,1.4fr)_120px_150px_auto_auto]">
        <span aria-hidden className="num grid size-6 place-items-center rounded-md bg-subtle text-xs font-semibold text-muted">{idea.rank}</span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{idea.customer}</span>
          <span className="block truncate text-xs text-muted">{idea.paid_count > 0 ? t("collections.avgDelay", { n: Math.round(idea.avg_delay), count: idea.paid_count }) : t("collections.noHistory")}</span>
        </span>
        <span className="num text-right text-sm font-semibold md:order-3 md:text-left"><span className="mr-1 text-xs font-normal text-muted md:hidden">{t("collections.open")}</span>{rm(idea.amount_open)}</span>
        <span className={cn("num col-start-2 text-[13px] font-medium md:order-4 md:col-start-auto", idea.effect_rm > 0 ? "text-allow" : "text-muted")}>{idea.effect_rm > 0 ? t("collections.effect", { rm: rm(idea.effect_rm) }) : t("collections.effect.none")}</span>
        <label className="col-start-2 flex items-center md:order-5 md:col-start-auto">
          <span className="sr-only">{t("collections.tone")} {idea.customer}</span>
          <select value={idea.tone} onChange={(e) => tone.mutate(e.target.value as "friendly" | "firm")}
            className="min-h-11 cursor-pointer rounded-lg border border-border bg-surface px-2 text-[13px] md:min-h-8">
            <option value="friendly">{t("tone.friendly")}</option><option value="firm">{t("tone.firm")}</option>
          </select>
        </label>
        <Button size="sm" variant="secondary" className="min-w-[92px] col-start-3 row-start-2 md:order-6 md:col-start-auto md:row-start-auto" onClick={() => setOpen(!open)} aria-expanded={open}>
          <Mail aria-hidden className="size-3.5" />{open ? t("collections.hide") : t("collections.preview")}
        </Button>
      </div>
      {open && (
        <Tabs defaultValue={lang} className="rise mt-3 border-t border-border pt-3">
          <TabsList><TabsTrigger value="ms">Bahasa Malaysia</TabsTrigger><TabsTrigger value="en">English</TabsTrigger></TabsList>
          {(["ms", "en"] as const).map((l) => (
            <TabsContent key={l} value={l} className="mt-3">
              <textarea readOnly value={text(l)} rows={8} aria-label={t("collections.draft")} className="w-full resize-y rounded-lg border border-border bg-subtle p-3 text-sm leading-relaxed" />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard?.writeText(text(l)); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                  <Copy aria-hidden className="size-4" />{copied ? t("collections.copied") : t("collections.copy")}
                </Button>
                <Button size="sm" onClick={() => chase.mutate()} disabled={chase.isPending} data-testid={`chase-${idea.customer_id}`}>{t("collections.send")}</Button>
                <span className="text-xs text-muted">{t("collections.demoNote")}</span>
              </div>
            </TabsContent>
          ))}
        </Tabs>
      )}
    </li>
  );
}
