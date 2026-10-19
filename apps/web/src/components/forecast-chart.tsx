"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis,
} from "recharts";
import { useT } from "@/i18n";
import type { Event, ForecastOut } from "@/lib/api";
import { fdate, rm } from "@/lib/format";

export type View = "unmanaged" | "managed";

const VERDICT_FILL: Record<string, string> = {
  ALLOW: "var(--allow)", HOLD: "var(--hold)", ESCALATE: "var(--escalate)", DENY: "var(--deny)",
};

function usePrefersReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setR(m.matches);
    const f = () => setR(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return r;
}

/** Triangles, not colour alone: bills point down, invoices point up. Shape + fill + label in the tooltip. */
function Marker(props: { cx?: number; cy?: number; payload?: { kind: string; verdict?: string | null } }) {
  const { cx = 0, cy = 0, payload } = props;
  if (!payload) return null;
  const up = payload.kind === "invoice";
  const fill = up ? "var(--chart-line)" : payload.verdict ? VERDICT_FILL[payload.verdict] : "var(--muted)";
  const d = up ? `M${cx},${cy - 6} L${cx + 5},${cy + 4} L${cx - 5},${cy + 4} Z` : `M${cx},${cy + 6} L${cx + 5},${cy - 4} L${cx - 5},${cy - 4} Z`;
  return <path d={d} fill={fill} stroke="var(--surface)" strokeWidth={1} />;
}

export function ForecastChart({
  data, view, height = 340, compact = false,
}: {
  data: ForecastOut;
  view: View;
  height?: number;
  compact?: boolean;
}) {
  const { t, lang } = useT();
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(max-width: 639px)");
    const f = () => setNarrow(m.matches);
    f();
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  const reducedPref = usePrefersReducedMotion();
  // First paint is instant; later changes (a what-if) animate the band redrawing.
  const [mounted, setMounted] = useState(false);
  useEffect(() => { const h = setTimeout(() => setMounted(true), 400); return () => clearTimeout(h); }, []);
  const reduced = reducedPref || !mounted;
  const band = data[view];
  const B = data.min_balance;

  const rows = useMemo(
    () =>
      data.days.map((date, i) => ({
        i, x: i + 1, date, p10: band.p10[i], p25: band.p25[i], p50: band.p50[i], p75: band.p75[i], p90: band.p90[i],
        base80: band.p10[i], w80: band.p90[i] - band.p10[i], base50: band.p25[i], w50: band.p75[i] - band.p25[i],
      })),
    [data.days, band],
  );
  const byDate = useMemo(() => {
    const m = new Map<string, Event[]>();
    for (const e of data.events) m.set(e.date, [...(m.get(e.date) ?? []), e]);
    return m;
  }, [data.events]);

  const lo = Math.min(...band.p10.slice(1), B) - 6000;
  const hi = Math.max(...band.p90) + 6000;
  const yMin = Math.floor((Math.min(lo, 0) - 14000) / 10000) * 10000; // room under zero for the event markers
  const yMax = Math.ceil(hi / 10000) * 10000;
  const idx = (iso: string) => Math.max(0, data.days.indexOf(iso));
  const X = (i: number) => i + 1; // Recharts treats an x of 0 as missing on a numeric axis
  const markerY = yMin + (yMax - yMin) * 0.04;
  const markers = data.events
    .filter((e) => e.kind !== "payroll" && e.kind !== "statutory")
    .map((e) => ({ x: X(idx(e.date)), y: markerY + (e.kind === "invoice" ? (yMax - yMin) * 0.045 : 0), kind: e.kind, verdict: e.verdict }));
  const step = compact ? 40000 : 20000;
  const yTicks: number[] = [];
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) yTicks.push(v);
  const ticks = data.days.map((_, i) => X(i)).filter((x) => (x - 1) % 14 === 0);
  const low = data.low;
  const lowIdx = idx(view === "unmanaged" ? low.worst_date : data.managed_low.date);
  const lowVal = view === "unmanaged" ? low.worst : data.managed_low.p10;

  const summary =
    view === "unmanaged"
      ? t("chart.summary.unmanaged", { low: rm(low.worst), date: fdate(low.worst_date, lang), min: rm(B) })
      : t("chart.summary.managed", { low: rm(data.managed_low.p10), date: fdate(data.managed_low.date, lang), min: rm(B) });

  return (
    <div role="img" aria-label={summary} style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 16, right: compact ? 8 : 20, bottom: 4, left: 0 }}>
          <XAxis
            type="number" dataKey="x" domain={[1, data.days.length]} ticks={compact ? ticks.filter((_, k) => k % 2 === 0) : ticks}
            tickFormatter={(x: number) => fdate(data.days[x - 1], lang)} stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }}
          />
          <YAxis
            domain={[yMin, yMax]} ticks={yTicks} width={compact ? 44 : 56} stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }}
            tickFormatter={(v: number) => (v < 0 ? `(${Math.abs(v / 1000)}k)` : `${v / 1000}k`)}
          />
          {/* ranges as a transparent base plus a visible width, stacked */}
          <Area dataKey="base80" stackId="r80" type="monotone" stroke="none" fill="transparent" isAnimationActive={false} activeDot={false} legendType="none" />
          <Area dataKey="w80" stackId="r80" type="monotone" stroke="none" fill="var(--chart-band)" fillOpacity={0.1} isAnimationActive={!reduced} animationDuration={200} animationEasing="ease-out" activeDot={false} />
          <Area dataKey="base50" stackId="r50" type="monotone" stroke="none" fill="transparent" isAnimationActive={false} activeDot={false} legendType="none" />
          <Area dataKey="w50" stackId="r50" type="monotone" stroke="none" fill="var(--chart-band)" fillOpacity={0.2} isAnimationActive={!reduced} animationDuration={200} animationEasing="ease-out" activeDot={false} />
          <Line dataKey="p50" type="monotone" stroke="var(--chart-line)" strokeWidth={2} dot={false} isAnimationActive={!reduced} animationDuration={200} animationEasing="ease-out" />
          <ReferenceLine y={B} stroke="var(--deny)" strokeDasharray="6 4" strokeWidth={1.5}
            label={{ value: `${t("chart.minimum")} ${rm(B)}`, position: "insideTopRight", fill: "var(--deny)", fontSize: 12, fontWeight: 600 }} />
          <ReferenceLine x={1} stroke="var(--muted)" strokeDasharray="2 3" label={{ value: t("chart.today"), position: "insideTopLeft", fill: "var(--muted)", fontSize: 11 }} />
          <ReferenceDot x={X(lowIdx)} y={lowVal} r={6} fill="var(--deny)" stroke="var(--surface)" strokeWidth={2}
            label={compact || narrow ? undefined : { value: `${rm(lowVal)} · ${fdate(data.days[lowIdx], lang)}`, position: lowIdx > 55 ? "left" : "right", fill: "var(--text)", fontSize: 12, fontWeight: 700 }} />
          <Scatter data={markers} dataKey="y" shape={<Marker />} isAnimationActive={false} legendType="none" />
          <Tooltip
            cursor={{ stroke: "var(--muted)", strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload.find((p) => p.payload?.date)?.payload as (typeof rows)[number] | undefined;
              if (!r) return null;
              const ev = byDate.get(r.date) ?? [];
              return (
                <div className="num max-w-[260px] rounded-lg border border-border bg-surface p-3 text-sm shadow-card">
                  <p className="font-semibold">{fdate(r.date, lang)}</p>
                  <p>{t("chart.balance")}: <b>{rm(r.p50)}</b></p>
                  <p className="text-muted">{t("chart.range80")}: {rm(r.p10)} – {rm(r.p90)}</p>
                  {ev.length > 0 && (
                    <ul className="mt-2 space-y-0.5 border-t border-border pt-2">
                      {ev.map((e) => (
                        <li key={e.id} className="flex justify-between gap-3">
                          <span className="truncate">{e.kind === "invoice" ? "▲" : "▼"} {e.label}</span>
                          <span className="shrink-0">{rm(e.amount)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
