"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Async } from "@/components/async";
import { CardsSkeleton, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { VerdictBadge } from "@/components/ui/verdict-badge";
import { useT } from "@/i18n";
import { api, unwrap, type Schemas } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { useAct, usePolicy } from "@/lib/hooks";

export default function PolicyPage() {
  const { t } = useT();
  const q = usePolicy();
  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("policy.title")} answer={t("policy.question")} /><CardsSkeleton n={2} /></>}>
      {(p) => <PolicyForm key={`${p.min_balance}-${p.risk_tolerance}-${p.approval_limit}-${p.protected_payees.join()}`} p={p} />}
    </Async>
  );
}

function PolicyForm({ p }: { p: Schemas["PolicyOut"] }) {
  const { t, lang, txt } = useT();
  const [min, setMin] = useState(p.min_balance);
  const [tol, setTol] = useState(p.risk_tolerance);
  const [limit, setLimit] = useState(p.approval_limit);
  const [prot, setProt] = useState<string[]>(p.protected_payees);
  const stop = Math.max(0, p.risk_options.findIndex((o) => Math.abs(1 - o - tol) < 1e-6));
  const dirty = min !== p.min_balance || tol !== p.risk_tolerance || limit !== p.approval_limit || prot.join("|") !== p.protected_payees.join("|");
  const body = useMemo(() => ({ min_balance: min, risk_tolerance: tol, approval_limit: limit, protected_payees: prot }), [min, tol, limit, prot]);

  const [debounced, setDebounced] = useState(body);
  useEffect(() => { const h = setTimeout(() => setDebounced(body), 350); return () => clearTimeout(h); }, [body]);
  const preview = useQuery({
    queryKey: ["policy-preview", debounced], enabled: dirty,
    queryFn: async () => unwrap(await api.POST("/policy/preview", { body: debounced })),
  });
  const save = useAct(async () => { unwrap(await api.PUT("/policy", { body })); return { message: t("policy.saved") }; });
  const valid = min >= 0 && limit > 0;

  return (
    <>
      <ScreenHeader title={t("policy.title")} answer={t("policy.answer", { min: rm(p.min_balance), sure: Math.round(p.required_confidence * 100), limit: rm(p.approval_limit) })}>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={!dirty} onClick={() => { setMin(p.min_balance); setTol(p.risk_tolerance); setLimit(p.approval_limit); setProt(p.protected_payees); }}>{t("policy.reset")}</Button>
          <Button disabled={!dirty || !valid || save.isPending} onClick={() => save.mutate()} data-testid="save-policy">{save.isPending ? t("policy.saving") : t("policy.save")}</Button>
        </div>
      </ScreenHeader>

      {dirty && (
        <Card className="rise mb-4 border-accent/50" role="status" aria-live="polite" data-testid="policy-preview">
          <p className="font-semibold">{t("policy.preview")}</p>
          {preview.data ? (
            <>
              <p className="num mt-1 text-sm">
                {(["ALLOW", "HOLD", "ESCALATE", "DENY"] as const).map((v) => `${t(`verdict.${v}`)}: ${preview.data.baseline[v]} → ${preview.data.counts[v]}`).join("  ·  ")}
              </p>
              {preview.data.changes.length > 0 && (
                <ul className="mt-2 space-y-1.5">{preview.data.changes.slice(0, 6).map((c, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
                    <VerdictBadge verdict={c.from as never} /><span aria-hidden>→</span><VerdictBadge verdict={c.to as never} />
                    <span className="font-medium">{c.payee}</span>{c.release_to && c.to !== "ALLOW" && <span className="num text-muted">{fdate(c.release_to, lang)}</span>}
                  </li>))}</ul>
              )}
            </>
          ) : <p className="text-sm text-muted">{t("common.loading")}</p>}
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Rule title={t("policy.min")} example={txt(p.examples.min_balance)}>
          <NumberField label={t("policy.min")} value={min} onChange={setMin} step={1000} />
        </Rule>

        <Rule title={t("policy.risk")} example={txt(p.examples.risk)}>
          <p className="num text-2xl font-bold" data-testid="sure-value">{t("policy.sure", { n: Math.round((1 - tol) * 100) })}</p>
          <SliderPrimitive.Root
            className="relative mt-3 flex h-11 w-full touch-none select-none items-center" min={0} max={p.risk_options.length - 1} step={1} value={[stop]}
            onValueChange={([i]) => setTol(Math.round((1 - p.risk_options[i]) * 1000) / 1000)} aria-label={t("policy.risk")}
          >
            <SliderPrimitive.Track className="relative h-2 grow rounded-full bg-border"><SliderPrimitive.Range className="absolute h-full rounded-full bg-accent" /></SliderPrimitive.Track>
            <SliderPrimitive.Thumb aria-label={t("policy.risk")} className="block size-6 cursor-grab rounded-full border-2 border-accent bg-surface shadow" aria-valuetext={t("policy.sure", { n: Math.round((1 - tol) * 100) })} />
          </SliderPrimitive.Root>
          <div className="num flex justify-between text-xs text-muted">{p.risk_options.map((o) => <span key={o}>{Math.round(o * 100)}%</span>)}</div>
          <div className="mt-1 flex justify-between text-xs text-muted"><span>{t("policy.risk.fewer")}</span><span>{t("policy.risk.more")}</span></div>
        </Rule>

        <Rule title={t("policy.limit")} example={txt(p.examples.approval)}>
          <NumberField label={t("policy.limit")} value={limit} onChange={setLimit} step={1000} />
        </Rule>

        <Rule title={t("policy.protected")} example={txt(p.examples.protected)}>
          <fieldset>
            <legend className="sr-only">{t("policy.protected")}</legend>
            <ul className="grid gap-1 sm:grid-cols-2">
              {p.suppliers.map((s) => (
                <li key={s.name}>
                  <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
                    <input type="checkbox" className="size-5 cursor-pointer accent-[var(--accent)]" checked={prot.includes(s.name)}
                      onChange={(e) => setProt(e.target.checked ? [...prot, s.name] : prot.filter((x) => x !== s.name))} />
                    {s.name}
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        </Rule>
      </div>

      <Card className="mt-4">
        <h2 className="mb-1 flex items-center gap-2 text-base font-bold"><Lock aria-hidden className="size-4 text-muted" />{t("policy.fixed")}</h2>
        <p className="text-sm text-muted">{txt(p.examples.statutory)}</p>
        <p className="mt-2 text-sm text-muted">{t("policy.readonly")}</p>
      </Card>
    </>
  );
}

function Rule({ title, example, children }: { title: string; example: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="text-base font-bold">{title}</h2>
      {children}
      <p className="mt-auto rounded-lg bg-bg p-3 text-sm text-muted">{example}</p>
    </Card>
  );
}

function NumberField({ label, value, onChange, step }: { label: string; value: number; onChange: (n: number) => void; step: number }) {
  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <span className="flex min-h-11 items-center rounded-lg border border-border bg-surface px-3 focus-within:outline focus-within:outline-2 focus-within:outline-accent">
        <span className="mr-2 font-semibold text-muted">RM</span>
        <input type="number" inputMode="numeric" min={0} step={step} value={Number.isNaN(value) ? "" : value}
          onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))} className="num w-full bg-transparent py-2 text-xl font-bold outline-none" />
      </span>
    </label>
  );
}
