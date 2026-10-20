"use client";

import { useInfiniteQuery, useMutation } from "@tanstack/react-query";
import { BadgeCheck, Landmark, OctagonAlert, ShieldAlert, ShieldCheck } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Fragment, Suspense, useEffect, useState } from "react";
import { Async } from "@/components/async";
import { AnchorCard } from "@/components/anchor-card";
import { PipelineSteps } from "@/components/pipeline-steps";
import { BlockSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n";
import { API_URL, api, unwrap, type Schemas } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { useAct, useAgents } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export default function AgentsPage() {
  return <Suspense fallback={<BlockSkeleton h={420} />}><Agents /></Suspense>;
}

function Agents() {
  const { t, lang } = useT();
  const q = useAgents();
  const kill = useAct(async (on: boolean) => unwrap(await api.POST("/kill-switch", { body: { on } })));
  const ledger = useAgentsLedger();

  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("agents.title")} answer={t("agents.question")} /><BlockSkeleton h={420} /></>}>
      {(d) => {
        const open = d.alerts.filter((a) => !a.resolved);
        return (
          <>
            <ScreenHeader title={t("agents.title")} answer={t("agents.answer", { rows: d.audit_rows, run: d.last_run?.id ?? "—" })} />

            <section className="mb-6" aria-labelledby="pipe">
              <h2 id="pipe" className="mb-0.5 text-base font-semibold">{t("agents.pipeline")}</h2>
              <p className="mb-3 text-[13px] text-muted">{t("agents.pipeline.sub")}</p>
              <PipelineSteps nodes={d.nodes} />
            </section>

            <div className="mb-4 grid gap-4 md:grid-cols-2">
              <Card data-testid="kill-card" className={cn(d.kill_switch && "border-deny")}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="flex items-center gap-2 text-base font-bold"><OctagonAlert aria-hidden className={cn("size-5", d.kill_switch ? "text-deny" : "text-muted")} />{t("agents.kill")}</h2>
                    <p className="mt-1 text-sm text-muted">{t("agents.kill.body")}</p>
                    <p className={cn("mt-2 text-sm font-semibold", d.kill_switch ? "text-deny" : "text-allow")} data-testid="kill-state">{d.kill_switch ? t("agents.kill.on") : t("agents.kill.off")}</p>
                  </div>
                  <Switch checked={d.kill_switch} disabled={kill.isPending} onCheckedChange={(v) => kill.mutate(v)} aria-label={t("agents.kill")} data-testid="kill-switch" />
                </div>
              </Card>
              <Card>
                <h2 className="mb-2 flex items-center gap-2 text-base font-bold"><ShieldCheck aria-hidden className="size-5 text-accent" />{t("agents.watchdog")}</h2>
                {open.length === 0 ? <p className="text-sm text-allow">{t("agents.watchdog.clear")}</p> : (
                  <ul className="space-y-2">{open.map((a) => <li key={a.id} className="flex gap-2 text-sm"><ShieldAlert aria-hidden className={cn("mt-0.5 size-4 shrink-0", a.level === "critical" ? "text-deny" : "text-hold")} /><span><b>{a.level === "critical" ? t("agents.critical") : t("agents.warn")}</b> {a.message}</span></li>)}</ul>
                )}
                <p className="mt-2 text-xs text-muted">{t("agents.watchdog.body")}</p>
              </Card>
            </div>

            <AuditSection rows={d.audit_rows} />

            <section className="mt-8" aria-labelledby="runlog">
              <h2 id="runlog" className="mb-3 text-base font-semibold">{t("agents.runlog")}</h2>
              <Card className="overflow-hidden p-0">
                <div className="max-h-96 overflow-auto" tabIndex={0} aria-label={t("agents.runlog")}>
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <caption className="sr-only">{t("agents.runlog")}</caption>
                    <thead className="sticky top-0 border-b border-border bg-bg text-xs uppercase tracking-wide text-muted"><tr><th scope="col" className="px-4 py-2">{t("agents.run")}</th><th scope="col" className="px-4 py-2">{t("agents.node")}</th><th scope="col" className="px-4 py-2">{t("agents.what")}</th><th scope="col" className="px-4 py-2 text-right">ms</th></tr></thead>
                    <tbody>
                      {d.log.map((l) => (
                        <tr key={l.id} className="border-b border-border last:border-0">
                          <td className="num whitespace-nowrap px-4 py-2"><span className="text-muted">{l.run_id}</span> <span className="text-xs text-muted">{fdate(l.sim_date, lang)} · {l.mode}</span></td>
                          <td className="whitespace-nowrap px-4 py-2 font-medium">{l.node}</td>
                          <td className={cn("px-4 py-2", l.status === "skipped" && "text-muted")}>{l.status === "skipped" ? `– ${l.summary}` : `✓ ${l.summary}`}</td>
                          <td className="num px-4 py-2 text-right text-muted">{l.ms}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </section>

            <section className="mt-8" aria-labelledby="ledger">
              <h2 id="ledger" className="mb-1 flex items-center gap-2 text-base font-semibold"><Landmark aria-hidden className="size-5" />{t("agents.ledger")}</h2>
              <p className="mb-3 text-sm text-muted">{t("agents.ledger.sub")}</p>
              <Card className="overflow-hidden p-0">
                {ledger.data && ledger.data.rows.length > 0 ? (
                  <div className="max-h-72 overflow-auto" tabIndex={0} aria-label={t("agents.ledger")}>
                    <table className="w-full min-w-[520px] text-left text-sm"><caption className="sr-only">{t("agents.ledger")}</caption>
                      <thead className="border-b border-border bg-bg text-xs uppercase tracking-wide text-muted"><tr><th scope="col" className="px-4 py-2">#</th><th scope="col" className="px-4 py-2">{t("agents.ledger.to")}</th><th scope="col" className="px-4 py-2 text-right">{t("table.amount")}</th><th scope="col" className="px-4 py-2">{t("agents.ledger.status")}</th></tr></thead>
                      <tbody className="num">{ledger.data.rows.map((r) => <tr key={r.id} className="border-b border-border last:border-0"><td className="px-4 py-2 text-muted">{r.id}</td><td className="px-4 py-2">{r.to}</td><td className="px-4 py-2 text-right">{rm(r.amount)}</td><td className="px-4 py-2">{r.status === "accepted" ? "✓ " + t("agents.ledger.accepted") : "✕ " + t("agents.ledger.rejected") + (r.reason ? ` (${r.reason})` : "")}</td></tr>)}</tbody>
                    </table>
                  </div>
                ) : <EmptyState title={t("agents.ledger.none")} />}
              </Card>
            </section>
          </>
        );
      }}
    </Async>
  );
}

function useAgentsLedger() {
  const { data } = useAgentsLedgerQuery();
  return { data };
}
import { useQuery } from "@tanstack/react-query";
function useAgentsLedgerQuery() {
  return useQuery({
    queryKey: ["ledger"], refetchInterval: 15000,
    queryFn: async (): Promise<{ rows: { id: number; to: string; amount: number; status: string; reason: string }[] }> => (await fetch(`${API_URL}/bank/ledger`)).json(),
  });
}

function AuditSection({ rows: total }: { rows: number }) {
  const { t } = useT();
  const params = useSearchParams();
  const audit = useInfiniteQuery({
    queryKey: ["audit"], initialPageParam: undefined as number | undefined,
    queryFn: async ({ pageParam }) => unwrap(await api.GET("/audit", { params: { query: { before: pageParam, limit: 40 } } })),
    getNextPageParam: (last) => (last.rows.length === 40 ? last.rows[last.rows.length - 1].id : undefined),
    refetchInterval: 15000,
  });
  const [verifyResult, setVerifyResult] = useState<Schemas["VerifyOut"] | null>(null);
  const verify = useMutation({ mutationFn: async () => unwrap(await api.POST("/audit/verify")), onSuccess: setVerifyResult });
  useEffect(() => { if (params.get("verify") === "1") verify.mutate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [open, setOpen] = useState<number | null>(null);
  const rows = audit.data?.pages.flatMap((p) => p.rows) ?? [];

  return (
    <section aria-labelledby="audit" className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="audit" className="text-base font-semibold">{t("agents.audit")}</h2>
          <p className="text-sm text-muted">{t("agents.audit.sub", { n: total })}</p>
        </div>
        <Button onClick={() => verify.mutate()} disabled={verify.isPending} data-testid="verify-chain"><BadgeCheck aria-hidden className="size-4" />{verify.isPending ? t("agents.verifying") : t("agents.verify")}</Button>
      </div>
      {verifyResult && (
        <Card role="status" data-testid="verify-result" className={cn("rise mb-3", verifyResult.ok ? "border-allow/60" : "border-deny")}>
          {verifyResult.ok
            ? <p className="flex items-center gap-2 font-semibold text-allow"><ShieldCheck aria-hidden className="size-5" />{t("agents.verify.ok", { n: verifyResult.checked })}</p>
            : <p className="flex items-center gap-2 font-semibold text-deny"><ShieldAlert aria-hidden className="size-5" />{t("agents.verify.bad", { row: verifyResult.broken_at ?? "?", reason: verifyResult.reason ?? "" })}</p>}
        </Card>
      )}
      <AnchorCard />
      <Card className="overflow-hidden p-0">
        <div className="max-h-[28rem] overflow-auto" tabIndex={0} aria-label={t("agents.audit")}>
          <table className="w-full min-w-[720px] text-left text-sm" data-testid="audit-table">
            <caption className="sr-only">{t("agents.audit")}</caption>
            <thead className="sticky top-0 border-b border-border bg-bg text-xs uppercase tracking-wide text-muted"><tr><th scope="col" className="px-3 py-2">#</th><th scope="col" className="px-3 py-2">{t("agents.audit.time")}</th><th scope="col" className="px-3 py-2">{t("agents.audit.actor")}</th><th scope="col" className="px-3 py-2">{t("agents.audit.event")}</th><th scope="col" className="px-3 py-2">{t("agents.audit.hash")}</th></tr></thead>
            <tbody className="num">
              {rows.map((r) => {
                const broken = verifyResult && !verifyResult.ok && verifyResult.broken_at === r.id;
                return (
                  <Fragment key={r.id}>
                    <tr className={cn("cursor-pointer border-b border-border hover:bg-subtle", broken && "bg-deny/10")} onClick={() => setOpen(open === r.id ? null : r.id)}>
                      <td className="px-3 py-2 text-muted">{broken ? "✕ " : ""}{r.id}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-muted">{r.ts.slice(11, 19)}</td>
                      <td className="px-3 py-2">{r.actor}</td>
                      <td className="px-3 py-2 font-medium"><button className="inline-flex min-h-11 cursor-pointer items-center text-left md:min-h-0" aria-expanded={open === r.id}>{r.event}</button></td>
                      <td className="px-3 py-2 font-mono text-xs text-muted">{r.hash.slice(0, 10)}…</td>
                    </tr>
                    {open === r.id && (
                      <tr className="border-b border-border bg-bg"><td colSpan={5} className="px-3 py-3 text-xs">
                        <pre className="whitespace-pre-wrap break-all font-mono">{JSON.stringify(r.payload, null, 1)}</pre>
                        <p className="mt-2 break-all font-mono text-muted">prev: {r.prev_hash}<br />hash: {r.hash}</p>
                      </td></tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          {audit.hasNextPage && <div className="p-3 text-center"><Button variant="secondary" size="sm" onClick={() => audit.fetchNextPage()} disabled={audit.isFetchingNextPage}>{t("agents.audit.more")}</Button></div>}
        </div>
      </Card>
    </section>
  );
}
