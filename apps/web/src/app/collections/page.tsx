"use client";

import { Check, Copy, Mail } from "lucide-react";
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
type Inv = Schemas["AgeInvoice"];

export default function CollectionsPage() {
  const { t, txt } = useT();
  const q = useCollections();
  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("collections.title")} answer={t("collections.question")} /><CardsSkeleton n={3} /></>}>
      {(d) => (
        <>
          <ScreenHeader title={t("collections.title")} answer={txt(d.summary)} />
          <section aria-labelledby="rank" className="mb-8">
            <h2 id="rank" className="mb-1 text-lg font-bold">{t("collections.rank")}</h2>
            <p className="mb-3 text-sm text-muted">{t("collections.rank.sub", { days: d.assumption_days })}</p>
            {d.ideas.length === 0 ? <EmptyState title={t("collections.none")} /> : (
              <ol className="space-y-3" data-testid="chase-ranking">{d.ideas.slice(0, 8).map((i) => <IdeaCard key={i.customer_id} idea={i} />)}</ol>
            )}
          </section>

          <section aria-labelledby="age" className="mb-8">
            <h2 id="age" className="mb-3 text-lg font-bold">{t("collections.ageing")}</h2>
            <div className="grid gap-3 md:grid-cols-4">
              {(["not_due", "d1_30", "d31_60", "d60"] as const).map((k) => {
                const list = d.ageing[k];
                const total = list.reduce((s, x) => s + x.amount, 0);
                return (
                  <Card key={k} className="flex flex-col gap-2 p-3">
                    <div>
                      <h3 className="text-sm font-bold">{t(`age.${k}` as Key)}</h3>
                      <p className="num text-sm text-muted">{rm(total)} · {list.length}</p>
                    </div>
                    {list.length === 0 ? <p className="text-xs text-muted">{t("collections.noneHere")}</p> : (
                      <ul className="space-y-2">{list.map((inv) => <InvoiceChip key={inv.id} inv={inv} />)}</ul>
                    )}
                  </Card>
                );
              })}
            </div>
          </section>

          <section aria-labelledby="dso">
            <h2 id="dso" className="mb-1 text-lg font-bold">{t("collections.dso")}</h2>
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

function InvoiceChip({ inv }: { inv: Inv }) {
  const { t, lang } = useT();
  return (
    <li className="rounded-lg border border-border bg-bg p-2 text-xs">
      <p className="truncate font-semibold">{inv.customer}</p>
      <p className="num flex justify-between gap-2"><span className="text-muted">{inv.number}</span><span className="font-semibold">{rm(inv.amount)}</span></p>
      <p className="num text-muted">
        {inv.days_overdue > 0 ? t("collections.late", { n: inv.days_overdue }) : t("decision.due", { date: fdate(inv.due, lang) })}
        {inv.expected ? ` · ${t("collections.expected", { date: fdate(inv.expected, lang) })}` : ""}
      </p>
      {inv.chased_on && <p className="mt-0.5 inline-flex items-center gap-1 font-semibold text-allow"><Check aria-hidden className="size-3" />{t("collections.chased", { date: fdate(inv.chased_on, lang) })}</p>}
      {inv.late_signal_days > 0 && <p className="mt-0.5 font-semibold text-hold">{t("collections.signal", { n: inv.late_signal_days })}</p>}
    </li>
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
    <li>
      <Card className="space-y-3">
        <div className="flex items-start gap-3">
          <span aria-hidden className="num grid size-9 shrink-0 place-items-center rounded-full bg-accent/10 text-sm font-bold text-accent">{idea.rank}</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="font-bold">{idea.customer}</h3>
              <p className="num text-sm"><span className="text-muted">{t("collections.open")}</span> <b>{rm(idea.amount_open)}</b></p>
            </div>
            <p className="num mt-1 text-base font-semibold text-allow">{idea.effect_rm > 0 ? t("collections.effect", { rm: rm(idea.effect_rm) }) : t("collections.effect.none")}</p>
            <p className="mt-1 text-sm text-muted">{idea.why}</p>
            <p className="mt-1 text-xs text-muted">{idea.paid_count > 0 ? t("collections.avgDelay", { n: Math.round(idea.avg_delay), count: idea.paid_count }) : t("collections.noHistory")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">{t("collections.tone")}</span>
            <select value={idea.tone} onChange={(e) => tone.mutate(e.target.value as "friendly" | "firm")} aria-label={`${t("collections.tone")} ${idea.customer}`}
              className="min-h-11 cursor-pointer rounded-lg border border-border bg-surface px-2 text-sm md:min-h-9">
              <option value="friendly">{t("tone.friendly")}</option><option value="firm">{t("tone.firm")}</option>
            </select>
          </label>
          <Button size="sm" variant="secondary" onClick={() => setOpen(!open)} aria-expanded={open}><Mail aria-hidden className="size-4" />{open ? t("collections.hide") : t("collections.preview")}</Button>
        </div>
        {open && (
          <Tabs defaultValue={lang} className="rise">
            <TabsList><TabsTrigger value="ms">Bahasa Malaysia</TabsTrigger><TabsTrigger value="en">English</TabsTrigger></TabsList>
            {(["ms", "en"] as const).map((l) => (
              <TabsContent key={l} value={l} className="mt-3">
                <textarea readOnly value={text(l)} rows={10} aria-label={t("collections.draft")} className="w-full resize-y rounded-lg border border-border bg-bg p-3 text-sm leading-relaxed" />
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" onClick={async () => { await navigator.clipboard?.writeText(text(l)); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                    <Copy aria-hidden className="size-4" />{copied ? t("collections.copied") : t("collections.copy")}
                  </Button>
                  <Button size="sm" onClick={() => chase.mutate()} disabled={chase.isPending} data-testid={`chase-${idea.customer_id}`}>{t("collections.send")}</Button>
                </div>
                <p className={cn("mt-2 text-xs text-muted")}>{t("collections.demoNote")}</p>
              </TabsContent>
            ))}
          </Tabs>
        )}
      </Card>
    </li>
  );
}
