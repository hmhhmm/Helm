"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { useState } from "react";
import { useT } from "@/i18n";
import { API_URL } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { Button } from "./ui/button";
import { Sheet } from "./ui/sheet";

type Doc = { number: string; status: string; document: { Invoice: { IssueDate: { _: string }[]; LegalMonetaryTotal: { PayableAmount: { _: number }[] }[] }[] } };

/** The MyInvois document for one invoice. It is generated from the ledger and has not been submitted to LHDN. */
export function EinvoiceButton({ invoiceId, number, customer }: { invoiceId: string; number: string; customer: string }) {
  const { t, lang } = useT();
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["einvoice", invoiceId], enabled: open,
    queryFn: async () => { const r = await fetch(`${API_URL}/invoices/${invoiceId}/einvoice`); if (!r.ok) throw new Error("x"); return (await r.json()) as Doc; },
  });
  const inv = q.data?.document.Invoice[0];
  const download = () => {
    if (!q.data) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(q.data.document, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${number}.json` });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <>
      <button onClick={() => setOpen(true)} aria-label={`${t("einv.title")} ${number}`} className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-md px-2 text-xs font-medium text-accent hover:bg-subtle md:min-h-8">
        <FileText aria-hidden className="size-3.5" />{t("einv.open")}
      </button>
      <Sheet open={open} onOpenChange={setOpen} title={`${t("einv.title")} ${number}`} description={customer} side="center">
        {q.isError ? <p role="alert" className="text-sm text-deny">{t("einv.failed")}</p> : !inv ? <div className="skeleton h-24" /> : (
          <div className="space-y-4">
            <span className="inline-flex items-center rounded-full bg-subtle px-2.5 py-1 text-xs font-medium text-hold">{t("einv.ready")}</span>
            <dl className="num grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted">{t("einv.issued")}</dt><dd className="text-right">{fdate(inv.IssueDate[0]._, lang)}</dd>
              <dt className="text-muted">{t("einv.total")}</dt><dd className="text-right font-semibold">{rm(inv.LegalMonetaryTotal[0].PayableAmount[0]._)}</dd>
              <dt className="text-muted">{t("einv.type")}</dt><dd />
            </dl>
            <p className="text-[13px] text-muted">{t("einv.note")}</p>
            <Button variant="secondary" className="w-full" onClick={download}><Download aria-hidden className="size-4" />{t("einv.download")}</Button>
          </div>
        )}
      </Sheet>
    </>
  );
}
