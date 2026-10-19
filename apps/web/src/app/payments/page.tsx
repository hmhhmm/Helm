"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { Async } from "@/components/async";
import { DecisionList, DecisionRow } from "@/components/decision-row";
import { useOverlays } from "@/components/overlays";
import { BlockSkeleton, EmptyState, ScreenHeader } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useT, type Key } from "@/i18n";
import type { Row } from "@/lib/api";
import { usePayments } from "@/lib/hooks";

export default function PaymentsPage() {
  return <Suspense fallback={<BlockSkeleton h={400} />}><Payments /></Suspense>;
}

function Payments() {
  const { t, txt } = useT();
  const q = usePayments();
  const params = useSearchParams();
  const { openDecision, openApproval } = useOverlays();
  const openId = params.get("open");
  useEffect(() => { if (openId) openDecision(openId); }, [openId, openDecision]);

  return (
    <Async q={q} skeleton={<><ScreenHeader title={t("payments.title")} answer={t("payments.question")} /><BlockSkeleton h={400} /></>}>
      {(d) => {
        const escal = [...d.groups.statutory, ...d.groups.due_soon, ...d.groups.can_wait].filter((r) => r.verdict === "ESCALATE" && r.status === "queued");
        const sections: { key: string; title: Key; help: Key; rows: Row[] }[] = [
          { key: "statutory", title: "payments.statutory", help: "payments.statutory.help", rows: d.groups.statutory },
          { key: "due_soon", title: "payments.dueSoon", help: "payments.dueSoon.help", rows: d.groups.due_soon },
          { key: "can_wait", title: "payments.canWait", help: "payments.canWait.help", rows: d.groups.can_wait },
          { key: "paid", title: "payments.paid", help: "payments.paid.help", rows: d.groups.paid },
        ];
        return (
          <>
            <ScreenHeader title={t("payments.title")} answer={txt(d.summary)} />
            {escal.length > 0 && (
              <Card className="mb-6 border-escalate/50" role="alert">
                <p className="font-semibold">{t("payments.needsYou", { n: escal.length })}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {escal.map((r) => <Button key={r.proposal_id} size="sm" variant="secondary" onClick={() => openApproval(r.proposal_id)}>{r.payee} · {t("today.review")}</Button>)}
                </div>
              </Card>
            )}
            {sections.map((s) => (
              <section key={s.key} aria-labelledby={`g-${s.key}`} className="mb-8" data-testid={`group-${s.key}`}>
                <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                  <h2 id={`g-${s.key}`} className="text-sm font-semibold">{t(s.title)} <span className="num text-[13px] font-normal text-muted">{s.rows.length}</span></h2>
                                  </div>
                {s.rows.length === 0 ? (s.key === "paid" ? null : <EmptyState title={t("payments.none")} />) : (
                  <DecisionList>
                    {s.rows.map((r) => <DecisionRow key={r.proposal_id} row={r} onOpen={() => openDecision(r.proposal_id)} />)}
                  </DecisionList>
                )}
              </section>
            ))}
          </>
        );
      }}
    </Async>
  );
}
