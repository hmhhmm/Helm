"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { useT } from "@/i18n";
import { api, unwrap } from "@/lib/api";
import { useAct } from "@/lib/hooks";
import { Button } from "./ui/button";
import { Sheet } from "./ui/sheet";

/** The owner enters a live payment. Helm checks it, and a payee it has not paid before waits for approval. */
export function NewPayment() {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [payee, setPayee] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const send = useAct(async () => {
    const r = unwrap(await api.POST("/payments/new", { body: { payee, amount: Number(amount), reference } }));
    setOpen(false); setPayee(""); setAmount(""); setReference("");
    return r;
  });
  const field = "min-h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:outline-2 focus:outline-accent";
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)} data-testid="new-payment"><Plus aria-hidden className="size-4" />{t("newpay.open")}</Button>
      <Sheet open={open} onOpenChange={setOpen} title={t("newpay.title")} description={t("newpay.sub")} side="center">
        <form onSubmit={(e) => { e.preventDefault(); send.mutate(); }} className="space-y-3">
          <label className="block text-sm font-medium">{t("newpay.payee")}<input value={payee} onChange={(e) => setPayee(e.target.value)} required minLength={2} maxLength={80} className={field + " mt-1"} /></label>
          <label className="block text-sm font-medium">{t("newpay.amount")}<input value={amount} onChange={(e) => setAmount(e.target.value)} required inputMode="decimal" pattern="[0-9]+(\\.[0-9]{1,2})?" className={field + " mt-1"} /></label>
          <label className="block text-sm font-medium">{t("newpay.ref")}<input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={35} className={field + " mt-1"} /></label>
          <Button type="submit" className="w-full" disabled={send.isPending || !payee || !amount}>{t("newpay.go")}</Button>
        </form>
      </Sheet>
    </>
  );
}
