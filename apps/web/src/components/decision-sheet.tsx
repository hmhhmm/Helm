"use client";

import { Check, Circle, Clock, FlaskConical, Minus } from "lucide-react";
import { useEffect, useRef } from "react";
import { useT, type Key } from "@/i18n";
import { api, unwrap } from "@/lib/api";
import { daysBetween, fdate, rm } from "@/lib/format";
import { useDecision } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { ApprovalCard } from "./approval-card";
import { DocView } from "./doc-view";
import { Trace } from "./trace";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/card";
import { Sheet } from "./ui/sheet";
import { VerdictBadge } from "./ui/verdict-badge";
import { useMutation } from "@tanstack/react-query";

const STEP_LABEL: Record<string, Key> = {
  read: "timeline.read", planned: "timeline.planned", policy: "timeline.policy", human: "timeline.human", executor: "timeline.executor", bank: "timeline.bank",
};

export function DecisionSheet({ id, tryToday, onClose }: { id: string | null; tryToday?: boolean; onClose: () => void }) {
  const { t, lang } = useT();
  const q = useDecision(id);
  const d = q.data;
  const tryIt = useMutation({
    mutationFn: async () => unwrap(await api.GET("/decisions/{proposal_id}/try", { params: { path: { proposal_id: id! } } })),
  });
  const autoDone = useRef<string | null>(null);
  const { mutate: runTry, reset: resetTry } = tryIt;
  useEffect(() => {
    if (id && tryToday && autoDone.current !== id && d) {
      autoDone.current = id;
      runTry();
    }
  }, [id, tryToday, d, runTry]);
  useEffect(() => { if (!id) { resetTry(); autoDone.current = null; } }, [id, resetTry]);

  const row = d?.row;
  const lateDays = row?.release_on && row.due ? daysBetween(row.due, row.release_on) : 0;
  return (
    <Sheet
      open={!!id}
      onOpenChange={(o) => !o && onClose()}
      title={row ? `${row.payee} · ${rm(row.amount)}` : t("common.loading")}
      description={row ? `${row.ref ?? ""} · ${t("decision.due", { date: fdate(row.due, lang) })}` : undefined}
    >
      {q.isPending && <div className="space-y-3"><Skeleton className="h-16" /><Skeleton className="h-32" /><Skeleton className="h-48" /></div>}
      {q.isError && <p role="alert">{(q.error as Error).message}</p>}
      {d && row && (
        <div className="space-y-6">
          <section aria-label={t("decision.verdict")} className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span key={row.verdict} className="stamp inline-block"><VerdictBadge verdict={row.verdict} /></span>
              {row.status === "sent" && <span className="text-sm font-semibold text-allow">{t("decision.sentOn", { date: fdate(row.sent_on, lang) })}</span>}
              {row.status === "held_by_owner" && <span className="text-sm font-semibold text-muted">{t("decision.heldByYou")}</span>}
              {row.release_on && row.status === "queued" && (
                <span className="num text-sm">
                  {t("decision.release", { date: fdate(row.release_on, lang) })}
                  {lateDays > 0 && <span className="text-muted"> · {t("decision.daysAfter", { n: lateDays })}</span>}
                </span>
              )}
              {!row.release_on && row.verdict === "HOLD" && <span className="text-sm text-muted">{t("decision.noSafeDate")}</span>}
            </div>
            <p className="rounded-lg border-l-4 border-accent bg-surface p-3 text-[15px] leading-relaxed">{lang === "ms" ? row.why_ms : row.why}</p>
            {row.previous_verdict && (row.previous_verdict !== row.verdict || row.previous_release_on !== row.release_on) && (
              <p className="text-sm text-muted">
                {t("decision.changed", { from: t(`verdict.${row.previous_verdict}` as Key), to: t(`verdict.${row.verdict}` as Key) })}
                {row.previous_release_on && row.release_on && row.previous_release_on !== row.release_on ? ` (${fdate(row.previous_release_on, lang)} → ${fdate(row.release_on, lang)})` : ""}
              </p>
            )}
          </section>

          {row.verdict === "ESCALATE" && row.status === "queued" && <ApprovalCard id={row.proposal_id} />}

          <section aria-label={t("decision.timeline")}>
            <ol className="flex items-start justify-between gap-1 overflow-x-auto pb-1">
              {d.timeline.map((s) => (
                <li key={s.key} className="flex min-w-14 flex-1 flex-col items-center gap-1 text-center">
                  <span className={cn("grid size-7 place-items-center rounded-full border",
                    s.status === "done" ? "border-allow bg-allow/10 text-allow" : s.status === "current" ? "border-escalate bg-escalate/10 text-escalate" : "border-border text-muted")}>
                    {s.status === "done" ? <Check aria-hidden className="size-4" /> : s.status === "current" ? <Clock aria-hidden className="size-4" /> : s.status === "na" ? <Minus aria-hidden className="size-4" /> : <Circle aria-hidden className="size-3" />}
                  </span>
                  <span className="text-[11px] leading-tight text-muted">{t(STEP_LABEL[s.key])}</span>
                  <span className="sr-only">{s.status}</span>
                </li>
              ))}
            </ol>
          </section>

          <section>
            <h3 className="mb-2 text-base font-bold">{t("decision.trace")}</h3>
            <Trace checks={d.checks as never} minBalance={d.min_balance} />
          </section>

          {d.plan && (
            <section>
              <h3 className="mb-2 text-base font-bold">{t("decision.plan")}</h3>
              <p className="rounded-lg border border-border bg-surface p-3 text-sm">
                {d.plan.plan_date ? t("decision.plan.date", { date: fdate(d.plan.plan_date as string, lang), n: d.plan.days_late as number }) : t("decision.plan.none")}
                <span className="text-muted"> · {t("decision.plan.by")}</span>
              </p>
            </section>
          )}

          {d.document && (
            <section>
              <h3 className="mb-2 text-base font-bold">{t("decision.read")}</h3>
              <DocView doc={d.document} />
            </section>
          )}

          {row.kind === "pay_bill" && row.status === "queued" && (
            <section>
              <Button variant="secondary" onClick={() => tryIt.mutate()} disabled={tryIt.isPending}>
                <FlaskConical aria-hidden className="size-4" />{t("decision.tryToday")}
              </Button>
              {tryIt.data && (
                <div className="rise mt-3 space-y-2 rounded-lg border border-border bg-surface p-3">
                  <p className="text-sm font-semibold">{t("decision.tryResult")}</p>
                  <div className="flex items-center gap-2"><VerdictBadge verdict={tryIt.data.verdict} />
                    {tryIt.data.release_on && tryIt.data.verdict !== "ALLOW" && <span className="num text-sm">{t("decision.release", { date: fdate(tryIt.data.release_on, lang) })}</span>}
                  </div>
                  <p className="text-sm">{lang === "ms" ? tryIt.data.why_ms : tryIt.data.why}</p>
                  <p className="text-xs text-muted">{t("decision.trySaved")}</p>
                </div>
              )}
            </section>
          )}

          {d.receipt && (
            <section>
              <h3 className="mb-2 text-base font-bold">{t("decision.receipt")}</h3>
              <p className="rounded-lg border border-border bg-surface p-3 text-sm">
                <span className="num font-semibold">{d.receipt.id as string}</span> · {d.receipt.bank as string}<br />
                {d.receipt.explanation as string}
              </p>
            </section>
          )}

          {d.history.length > 1 && (
            <section>
              <h3 className="mb-2 text-base font-bold">{t("decision.history")}</h3>
              <ul className="space-y-2">
                {[...d.history].reverse().map((h, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <VerdictBadge verdict={h.verdict as never} />
                    <span className="text-muted">{h.release_on ? fdate(h.release_on as string, lang) : "—"}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </Sheet>
  );
}
