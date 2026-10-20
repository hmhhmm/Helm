"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_URL } from "@/lib/api";
import { getToken, LOGIN_EVENT } from "@/lib/auth";
import { cn } from "@/lib/utils";

type AnchorRow = { kind: string; seq: number; hash: string; tx_hash: string | null; block: number | null; chain_id: number | null; status: string; at: string };
type Status = { enabled: boolean; contract: string | null; explorer_tx: string; anchors: AnchorRow[] };
type Verify = { ok: boolean; checked: number; anchors: { seq: number; tx_hash: string | null; on_chain: boolean; database_matches: boolean; ok: boolean }[] };

async function call<T>(path: string, method = "GET"): Promise<T> {
  const token = getToken();
  const r = await fetch(`${API_URL}${path}`, { method, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  const body = await r.json().catch(() => ({}));
  if (r.status === 401) window.dispatchEvent(new Event(LOGIN_EVENT));
  if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : r.statusText);
  return body as T;
}

/** Shows the hashes written to a public test network and lets the owner check the log against them. Only hashes leave the system. */
export function AnchorCard() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["anchor"], queryFn: () => call<Status>("/anchor"), refetchInterval: 20000 });
  const [verify, setVerify] = useState<Verify | null>(null);
  const run = useMutation({ mutationFn: () => call("/anchor/run", "POST"), onSuccess: () => qc.invalidateQueries({ queryKey: ["anchor"] }) });
  const check = useMutation({ mutationFn: () => call<Verify>("/anchor/verify", "POST"), onSuccess: setVerify });
  const s = status.data;
  if (!s) return null;
  const audit = s.anchors.filter((a) => a.kind === "audit");

  return (
    <Card className="mb-3" data-testid="anchor-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-sm font-semibold"><Link2 aria-hidden className="size-4" />On-chain anchor</h3>
          <p className="mt-0.5 text-[13px] text-muted">
            {s.enabled ? `Audit and policy hashes on a public test network. Contract ${s.contract}.` : "Not configured. Hashes only ever leave Helm, never business data."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={!s.enabled || run.isPending} onClick={() => run.mutate()} data-testid="anchor-run">{run.isPending ? "Anchoring…" : "Anchor now"}</Button>
          <Button size="sm" disabled={!s.enabled || check.isPending} onClick={() => check.mutate()} data-testid="anchor-verify">{check.isPending ? "Checking…" : "Verify on-chain"}</Button>
        </div>
      </div>
      {(run.error || check.error) && <p role="alert" className="mt-2 text-sm text-deny">{((run.error ?? check.error) as Error).message}</p>}
      {verify && (
        <p role="status" className={cn("mt-2 flex items-center gap-2 text-sm font-semibold", verify.ok ? "text-allow" : "text-deny")} data-testid="anchor-verify-result">
          {verify.ok ? <ShieldCheck aria-hidden className="size-4" /> : <ShieldAlert aria-hidden className="size-4" />}
          {verify.ok ? `All ${verify.checked} anchors match the chain and the database.` : "An anchor does not match. The log may have changed after it was anchored."}
        </p>
      )}
      {audit.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-muted">
          {audit.slice(0, 5).map((a) => (
            <li key={a.tx_hash ?? a.at} className="truncate">
              Row {a.seq} · <span className="font-mono">{a.hash.slice(0, 12)}…</span> ·{" "}
              {a.tx_hash && <a className="text-accent underline" href={`${s.explorer_tx}${a.tx_hash}`} target="_blank" rel="noreferrer">{a.tx_hash.slice(0, 14)}…</a>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
