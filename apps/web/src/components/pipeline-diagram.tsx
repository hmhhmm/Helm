"use client";

import { useState } from "react";
import { useT } from "@/i18n";
import type { Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

type Kind = "agent" | "code" | "store" | "human";
interface N { id: string; label: string; col: number; row: number; kind: Kind; api?: string; n?: number }

const COL = 128, W = 112, H = 58, X0 = 8, ROW = [8, 108, 228, 348];
const NODES: N[] = [
  { id: "collections", label: "Collections Agent", col: 2, row: 0, kind: "agent", api: "collections", n: 2 },
  { id: "chase", label: "Chase ideas", col: 3, row: 0, kind: "store" },
  { id: "inputs", label: "Inputs", col: 0, row: 1, kind: "store" },
  { id: "reader", label: "Reader Agent", col: 1, row: 1, kind: "agent", api: "reader", n: 0 },
  { id: "facts", label: "Facts", col: 2, row: 1, kind: "store" },
  { id: "forecaster", label: "Forecaster Agent", col: 3, row: 1, kind: "agent", api: "forecaster", n: 1 },
  { id: "range", label: "Cash range", col: 4, row: 1, kind: "store" },
  { id: "scheduler", label: "Scheduler Agent", col: 5, row: 1, kind: "agent", api: "scheduler", n: 3 },
  { id: "plan", label: "Bill plan", col: 6, row: 1, kind: "store" },
  { id: "treasury", label: "Treasury Agent", col: 7, row: 1, kind: "agent", api: "treasury", n: 4 },
  { id: "proposals", label: "Proposals", col: 7, row: 2, kind: "store" },
  { id: "policy", label: "Policy Engine", col: 6, row: 2, kind: "code", api: "policy" },
  { id: "decisions", label: "Decisions", col: 5, row: 2, kind: "store" },
  { id: "human", label: "Human Review", col: 4, row: 2, kind: "human", api: "human" },
  { id: "executor", label: "Executor", col: 3, row: 2, kind: "code", api: "executor" },
  { id: "instruction", label: "Instruction", col: 2, row: 2, kind: "store" },
  { id: "bank", label: "Demo bank", col: 1, row: 2, kind: "store" },
  { id: "receipt", label: "Receipt", col: 0, row: 2, kind: "store" },
  { id: "explainer", label: "Explainer Agent", col: 0, row: 3, kind: "agent", api: "explainer", n: 5 },
  { id: "brief", label: "CFO brief (PDF)", col: 1, row: 3, kind: "store" },
  { id: "watchdog", label: "Watchdog", col: 5, row: 3, kind: "code", api: "watchdog" },
  { id: "audit", label: "Audit log", col: 6, row: 3, kind: "store" },
  { id: "cashpolicy", label: "Cash policy", col: 7, row: 3, kind: "store" },
];
const pos = (n: N) => ({ x: X0 + n.col * COL, y: ROW[n.row] });
const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));
const EDGES: [string, string][] = [
  ["inputs", "reader"], ["reader", "facts"], ["facts", "forecaster"], ["forecaster", "range"], ["range", "scheduler"], ["scheduler", "plan"], ["plan", "treasury"],
  ["facts", "collections"], ["collections", "chase"], ["treasury", "proposals"], ["proposals", "policy"], ["policy", "decisions"], ["decisions", "human"], ["human", "executor"],
  ["executor", "instruction"], ["instruction", "bank"], ["bank", "receipt"], ["receipt", "explainer"], ["explainer", "brief"], ["cashpolicy", "policy"], ["policy", "audit"], ["audit", "watchdog"],
];

function edgePath(a: N, b: N): string {
  const pa = pos(a), pb = pos(b);
  const ca = { x: pa.x + W / 2, y: pa.y + H / 2 }, cb = { x: pb.x + W / 2, y: pb.y + H / 2 };
  if (a.row === b.row) {
    const dir = cb.x > ca.x ? 1 : -1;
    return `M${ca.x + dir * (W / 2)},${ca.y} L${cb.x - dir * (W / 2) - dir * 3},${cb.y}`;
  }
  if (a.col === b.col) {
    const dir = cb.y > ca.y ? 1 : -1;
    return `M${ca.x},${ca.y + dir * (H / 2)} L${cb.x},${cb.y - dir * (H / 2) - dir * 3}`;
  }
  return `M${ca.x},${ca.y - (cb.y > ca.y ? -1 : 1) * (H / 2)} L${cb.x},${cb.y + (cb.y > ca.y ? -1 : 1) * (H / 2)}`;
}

function wrap(s: string): string[] {
  const words = s.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > 15) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
  }
  lines.push(cur);
  return lines.slice(0, 2);
}

export function PipelineDiagram({ nodes, onSelect, selected }: { nodes: Schemas["Node"][]; onSelect: (id: string) => void; selected: string | null }) {
  const { t } = useT();
  const [hover, setHover] = useState<string | null>(null);
  const api = Object.fromEntries(nodes.map((n) => [n.id, n]));
  return (
    <svg viewBox="0 0 1032 420" className="hidden w-full md:block" role="group" aria-label={t("agents.diagram")}>
      <defs>
        <marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--muted)" /></marker>
      </defs>
      {EDGES.map(([a, b]) => <path key={`${a}-${b}`} d={edgePath(byId[a], byId[b])} stroke="var(--muted)" strokeWidth="1.5" fill="none" markerEnd="url(#arr)" opacity={hover && hover !== a && hover !== b ? 0.25 : 0.9} />)}
      {/* ALLOW goes straight from the decision to the Executor; only ESCALATE detours through the owner */}
      <path d={`M${pos(byId.decisions).x + 20},${pos(byId.decisions).y + H} Q${pos(byId.human).x + W / 2 + 60},${pos(byId.human).y + H + 56} ${pos(byId.executor).x + W - 10},${pos(byId.executor).y + H + 3}`} stroke="var(--allow)" strokeWidth="1.5" fill="none" strokeDasharray="5 4" markerEnd="url(#arr)" />
      <text x={pos(byId.human).x + 10} y={pos(byId.human).y + H + 52} fontSize="11" fill="var(--muted)">if ALLOW</text>
      <text x={pos(byId.decisions).x - 12} y={pos(byId.decisions).y - 6} fontSize="11" fill="var(--muted)">if ESCALATE</text>
      {NODES.map((n) => {
        const p = pos(n);
        const a = api[n.api ?? ""] ;
        const step = a?.step;
        const status = n.api ? (step ? (step.status === "skipped" ? "– " + t("agents.skipped") : `✓ ${step.ms} ms`) : "") : n.kind === "store" ? t("agents.table") : "";
        const lines = wrap(n.label);
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} tabIndex={n.api ? 0 : -1} role={n.api ? "button" : undefined}
            aria-pressed={n.api ? selected === n.api : undefined}
            onClick={() => n.api && onSelect(n.api)} onKeyDown={(e) => { if (n.api && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onSelect(n.api); } }}
            onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} className={cn(n.api && "cursor-pointer")} data-testid={`node-${n.id}`}>
            <rect width={W} height={H} rx={10} fill={`var(--n-${n.kind})`} stroke={selected === n.api && n.api ? "var(--accent)" : `var(--n-${n.kind}-b)`} strokeWidth={selected === n.api && n.api ? 3 : 1.5} />
            {n.n !== undefined && (<><circle cx={12} cy={12} r={9} fill="var(--surface)" stroke={`var(--n-${n.kind}-b)`} /><text x={12} y={16} textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--text)">{n.n}</text></>)}
            {n.kind === "code" && <text x={W - 8} y={14} textAnchor="end" fontSize="9" fontWeight="700" fill="var(--text)">CODE</text>}
            {n.kind === "human" && <text x={W - 8} y={14} textAnchor="end" fontSize="9" fontWeight="700" fill="var(--text)">HUMAN</text>}
            {lines.map((l, i) => <text key={i} x={W / 2} y={(lines.length === 1 ? 31 : 25) + i * 13} textAnchor="middle" fontSize="12" fontWeight="700" fill="var(--text)">{l}</text>)}
            <text x={W / 2} y={H - 7} textAnchor="middle" fontSize="10" fill="var(--text)" opacity="0.75">{status}</text>
          </g>
        );
      })}
    </svg>
  );
}
