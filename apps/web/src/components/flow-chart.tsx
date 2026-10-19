"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useT } from "@/i18n";
import { rm } from "@/lib/format";

export interface FlowPoint { key: string; label: string; money_in: number; money_out: number }

/** Money in vs money out, side by side. Click a bar group to see what is behind it. */
export function FlowChart({
  data, height = 260, selected, onSelect, ariaLabel,
}: {
  data: FlowPoint[];
  height?: number;
  selected?: string | null;
  onSelect?: (key: string) => void;
  ariaLabel: string;
}) {
  const { t } = useT();
  const max = Math.max(1, ...data.map((d) => Math.max(d.money_in, d.money_out)));
  const step = max > 120_000 ? 40_000 : max > 60_000 ? 20_000 : 10_000;
  const top = Math.ceil(max / step) * step;
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step);
  return (
    <div role="img" aria-label={ariaLabel} style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={3} onClick={(e) => { const k = (e as { activePayload?: { payload: FlowPoint }[] } | null)?.activePayload?.[0]?.payload.key; if (k && onSelect) onSelect(k); }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }} interval="preserveStartEnd" />
          <YAxis width={48} domain={[0, top]} ticks={ticks} stroke="var(--border)" tick={{ fill: "var(--muted)", fontSize: 12 }} tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} />
          <Tooltip
            cursor={{ fill: "var(--subtle)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as FlowPoint;
              return (
                <div className="num rounded-lg border border-border bg-surface p-3 text-sm shadow-card">
                  <p className="font-semibold">{p.label}</p>
                  <p className="text-allow">▲ {t("flow.in")}: {rm(p.money_in)}</p>
                  <p>▼ {t("flow.out")}: {rm(p.money_out)}</p>
                  <p className="mt-1 border-t border-border pt-1 text-muted">{t("flow.net")}: {rm(p.money_in - p.money_out)}</p>
                </div>
              );
            }}
          />
          <Bar dataKey="money_in" radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={22}>
            {data.map((d) => <Cell key={d.key} fill="var(--allow)" fillOpacity={selected && selected !== d.key ? 0.4 : 1} cursor={onSelect ? "pointer" : undefined} />)}
          </Bar>
          <Bar dataKey="money_out" radius={[3, 3, 0, 0]} isAnimationActive={false} maxBarSize={22}>
            {data.map((d) => <Cell key={d.key} fill="var(--chart-line)" fillOpacity={selected && selected !== d.key ? 0.4 : 1} cursor={onSelect ? "pointer" : undefined} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function FlowLegend() {
  const { t } = useT();
  return (
    <ul className="mt-2 flex gap-5 text-xs text-muted">
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block size-2.5 rounded-sm bg-allow" />▲ {t("flow.in")}</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block size-2.5 rounded-sm" style={{ background: "var(--chart-line)" }} />▼ {t("flow.out")}</li>
    </ul>
  );
}
