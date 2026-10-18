"use client";

import { FileText, ShieldAlert } from "lucide-react";
import { useT } from "@/i18n";
import type { Schemas } from "@/lib/api";
import { fdate, rm } from "@/lib/format";
import { cn } from "@/lib/utils";

const INJECTION = /(ignore|disregard|override|system notice|do not tell|pay .{0,40}(today|now))/i;

/** What Helm read: the raw document next to the clean facts the Reader (which has no tools) extracted. */
export function DocView({ doc }: { doc: Schemas["DocumentOut"] }) {
  const { t, lang } = useT();
  const ex = doc.extracted as Record<string, unknown> | null;
  const lines = doc.raw_text.split("\n");
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {doc.quarantined ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-deny/40 bg-deny/10 px-2.5 py-1 text-xs font-semibold text-deny">
            <ShieldAlert aria-hidden className="size-3.5" /> {t("doc.quarantined")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-allow/40 bg-allow/10 px-2.5 py-1 text-xs font-semibold text-allow">
            <FileText aria-hidden className="size-3.5" /> {t("doc.readOk")}
          </span>
        )}
        <span className="text-xs text-muted">{t("doc.received", { date: fdate(doc.received_on, lang), source: doc.source.replace("_", " ") })}</span>
      </div>
      {doc.quarantined && <p className="rounded-lg border border-deny/30 bg-deny/5 p-3 text-sm">{t("doc.quarantined.explain")}</p>}
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("doc.raw")}</p>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-border bg-surface p-3 text-xs leading-relaxed">
          {lines.map((l, i) => (
            <span key={i} className={cn("block", INJECTION.test(l) && "rounded bg-deny/10 font-semibold text-deny")}>{l || " "}</span>
          ))}
        </pre>
      </div>
      {ex && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("doc.extracted")}</p>
          <dl className="num grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded-lg border border-border bg-surface p-3 text-sm">
            {(["counterparty", "reference", "amount", "issue_date", "due_date", "bank_account", "flags"] as const).map((k) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd className="break-words font-medium">
                  {k === "amount" ? rm(ex[k] as number) : Array.isArray(ex[k]) ? ((ex[k] as string[]).join(", ") || "—") : String(ex[k] ?? "—")}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-1 text-xs text-muted">{t("doc.schema")}</p>
        </div>
      )}
    </div>
  );
}
