"use client";

import { Check, ChevronRight, FileText, LineChart, ListChecks, Minus, Send, ShieldCheck, UserCheck } from "lucide-react";
import { useT, type Key } from "@/i18n";
import type { Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

type Who = "ai" | "rules" | "you";
const STEPS: { id: string; icon: typeof Check; title: Key; body: Key; who: Who; also?: string[] }[] = [
  { id: "reader", icon: FileText, title: "pipe.read", body: "pipe.read.body", who: "ai" },
  { id: "forecaster", icon: LineChart, title: "pipe.forecast", body: "pipe.forecast.body", who: "ai" },
  { id: "scheduler", icon: ListChecks, title: "pipe.plan", body: "pipe.plan.body", who: "ai", also: ["collections", "treasury"] },
  { id: "policy", icon: ShieldCheck, title: "pipe.check", body: "pipe.check.body", who: "rules" },
  { id: "human", icon: UserCheck, title: "pipe.approve", body: "pipe.approve.body", who: "you" },
  { id: "executor", icon: Send, title: "pipe.pay", body: "pipe.pay.body", who: "rules" },
];
const WHO: Record<Who, Key> = { ai: "pipe.who.ai", rules: "pipe.who.rules", you: "pipe.who.you" };

/** The pipeline in six plain steps. The detailed agent graph stays in the code, not on the screen. */
export function PipelineSteps({ nodes }: { nodes: Schemas["Node"][] }) {
  const { t } = useT();
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  return (
    <ol className="grid gap-3 md:grid-cols-6" aria-label={t("agents.diagram")}>
      {STEPS.map((s, i) => {
        const step = byId[s.id]?.step;
        const ran = step && step.status !== "skipped";
        const Icon = s.icon;
        return (
          <li key={s.id} className="relative flex md:block">
            <div className="flex-1 rounded-lg border border-border bg-surface p-3.5" data-testid={`step-${s.id}`}>
              <div className="flex items-center justify-between">
                <span aria-hidden className="grid size-8 place-items-center rounded-md bg-subtle text-muted"><Icon className="size-4" /></span>
                <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium", s.who === "rules" ? "bg-accent-solid/15 text-accent" : s.who === "you" ? "bg-allow/10 text-allow" : "bg-subtle text-muted")}>{t(WHO[s.who])}</span>
              </div>
              <p className="mt-3 text-sm font-semibold"><span className="num mr-1 text-muted">{i + 1}.</span>{t(s.title)}</p>
              <p className="mt-1 text-[13px] leading-snug text-muted">{t(s.body)}</p>
              <p className={cn("mt-3 flex items-center gap-1.5 text-xs", ran ? "text-allow" : "text-muted")}>
                {ran ? <Check aria-hidden className="size-3.5" /> : <Minus aria-hidden className="size-3.5" />}
                {ran ? t("pipe.ran", { ms: step!.ms }) : t("pipe.idle")}
              </p>
            </div>
            {i < STEPS.length - 1 && <ChevronRight aria-hidden className="absolute -right-2.5 top-1/2 hidden size-4 -translate-y-1/2 text-muted md:block" />}
          </li>
        );
      })}
    </ol>
  );
}
