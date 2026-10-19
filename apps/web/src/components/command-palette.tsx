"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useQueryClient } from "@tanstack/react-query";
import { CornerDownLeft, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { useT } from "@/i18n";
import { API_URL, api, unwrap } from "@/lib/api";
import { rm } from "@/lib/format";
import { useAct, useAppState, useCollections, usePayments } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { useOverlays } from "./overlays";
import { useTheme } from "./theme-toggle";

interface Item { id: string; label: string; hint?: string; group: string; run: () => void }

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, lang, setLang } = useT();
  const router = useRouter();
  const { openDecision, openSimulator } = useOverlays();
  const { toggle: toggleTheme } = useTheme();
  const payments = usePayments();
  const collections = useCollections();
  const appState = useAppState();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const sim = useAct(async (path: "/sim/advance-week" | "/sim/customer-late" | "/sim/malicious-invoice" | "/sim/reset") => unwrap(await api.POST(path)));
  const kill = useAct(async (on: boolean) => unwrap(await api.POST("/kill-switch", { body: { on } })));
  const close = () => { onOpenChange(false); setQuery(""); setActive(0); };
  const go = (href: string) => () => { close(); router.push(href); };

  const items = useMemo<Item[]>(() => {
    const out: Item[] = [];
    const nav: [string, string, string][] = [["/", t("nav.today"), "home"], ["/forecast", t("nav.forecast"), "chart"], ["/payments", t("nav.payments"), "bills"], ["/collections", t("nav.collections"), "invoices chase"], ["/cash", t("nav.cash"), "reserve sweep"], ["/policy", t("nav.policy"), "rules"], ["/agents", t("nav.agents"), "audit log verify"]];
    for (const [href, label, kw] of nav) out.push({ id: `nav-${href}`, label: `${t("palette.go")} ${label}`, hint: kw, group: t("palette.nav"), run: go(href) });
    const groups = payments.data?.groups;
    if (groups) {
      for (const r of [...groups.due_soon, ...groups.can_wait]) {
        out.push({ id: `pay-${r.proposal_id}`, label: t("palette.pay", { payee: r.payee, amount: rm(r.amount) }), hint: "pay bill try", group: t("palette.bills"), run: () => { close(); openDecision(r.proposal_id, { tryToday: true }); } });
      }
    }
    const seen = new Set<string>();
    for (const i of collections.data?.ideas ?? []) {
      if (seen.has(i.customer_id)) continue;
      seen.add(i.customer_id);
      out.push({ id: `late-${i.customer_id}`, label: t("palette.whatif", { customer: i.customer, days: 20 }), hint: "what if late", group: t("palette.whatifs"), run: go(`/forecast?late=${i.customer_id}:20`) });
    }
    out.push(
      { id: "a-advance", label: t("sim.advance"), group: t("palette.actions"), run: () => { close(); sim.mutate("/sim/advance-week"); } },
      { id: "a-late", label: t("sim.late"), group: t("palette.actions"), run: () => { close(); sim.mutate("/sim/customer-late"); } },
      { id: "a-bad", label: t("sim.bad"), group: t("palette.actions"), run: () => { close(); sim.mutate("/sim/malicious-invoice"); } },
      { id: "a-sim", label: t("palette.openSim"), group: t("palette.actions"), run: () => { close(); openSimulator(); } },
      { id: "a-verify", label: t("palette.verify"), group: t("palette.actions"), run: go("/agents?verify=1") },
      { id: "a-brief", label: t("palette.brief"), group: t("palette.actions"), run: () => { close(); window.open(`${API_URL}/brief.pdf`, "_blank"); } },
      { id: "a-kill", label: appState.data?.kill_switch ? t("palette.killOff") : t("palette.killOn"), group: t("palette.actions"), run: () => { close(); kill.mutate(!appState.data?.kill_switch); } },
      { id: "a-lang", label: lang === "en" ? "Bahasa Malaysia" : "English", hint: "language bahasa", group: t("palette.settings"), run: () => { close(); setLang(lang === "en" ? "ms" : "en"); } },
      { id: "a-theme", label: t("theme.toggle"), hint: "dark light", group: t("palette.settings"), run: () => { close(); toggleTheme(); } },
      { id: "a-reset", label: t("sim.reset"), group: t("palette.settings"), run: () => { close(); sim.mutate("/sim/reset"); qc.invalidateQueries(); } },
    );
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, lang, payments.data, collections.data, appState.data?.kill_switch]);

  const filtered = useMemo(() => {
    const toks = query.toLowerCase().split(/\s+/).filter(Boolean);
    return items.filter((i) => toks.every((k) => `${i.label} ${i.hint ?? ""} ${i.group}`.toLowerCase().includes(k))).slice(0, 14);
  }, [items, query]);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, filtered.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); filtered[active]?.run(); }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Dialog.Content aria-describedby={undefined} className="fixed left-1/2 top-[12vh] z-50 w-[calc(100%-32px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-card border border-border bg-surface shadow-card outline-none">
          <Dialog.Title className="sr-only">{t("palette.title")}</Dialog.Title>
          <div className="flex items-center gap-3 border-b border-border px-4">
            <Search aria-hidden className="size-5 text-muted" />
            <input
              autoFocus value={query} onChange={(e) => { setQuery(e.target.value); setActive(0); }} onKeyDown={onKey}
              role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={filtered[active] ? `opt-${filtered[active].id}` : undefined}
              placeholder={t("palette.placeholder")} className="min-h-14 flex-1 bg-transparent text-base outline-none placeholder:text-muted"
            />
          </div>
          <ul id="palette-list" role="listbox" ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
            {filtered.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">{t("palette.none")}</li>}
            {filtered.map((it, i) => (
              <li key={it.id} id={`opt-${it.id}`} role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={it.run}
                className={cn("flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-lg px-3 text-sm", i === active ? "bg-grad text-on-grad shadow-glow" : "hover:bg-bg")}>
                <span className="truncate">{it.label}</span>
                <span className={cn("flex shrink-0 items-center gap-1 text-xs", i === active ? "opacity-80" : "text-muted")}>{it.group}{i === active && <CornerDownLeft aria-hidden className="size-3" />}</span>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
