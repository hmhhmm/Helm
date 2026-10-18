"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { ApprovalCard } from "@/components/approval-card";
import { useT } from "@/i18n";

/** The page a phone opens from a message: one card, one tap. */
export default function ApprovePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t } = useT();
  return (
    <main className="mx-auto min-h-dvh w-full max-w-md px-4 py-6">
      <div className="mb-3 flex items-center justify-between">
        <Link href="/" className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-accent"><ArrowLeft aria-hidden className="size-4" />{t("approval.back")}</Link>
        <span className="rounded-full border border-border bg-surface px-3 py-1 text-[11px] font-semibold text-muted">{t("synthetic")}</span>
      </div>
      <h1 className="mb-3 text-xl font-bold">{t("approval.title")}</h1>
      <ApprovalCard id={id} />
    </main>
  );
}
