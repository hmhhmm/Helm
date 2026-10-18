"use client";

import { Check, Clock, ShieldAlert, User } from "lucide-react";
import { useT, type Key } from "@/i18n";
import { cn } from "@/lib/utils";

export type Verdict = "ALLOW" | "HOLD" | "ESCALATE" | "DENY";

// Status is never colour alone: each verdict has an icon and a word.
const META: Record<Verdict, { key: Key; Icon: typeof Check; cls: string }> = {
  ALLOW: { key: "verdict.ALLOW", Icon: Check, cls: "text-allow border-allow/40 bg-allow/10" },
  HOLD: { key: "verdict.HOLD", Icon: Clock, cls: "text-hold border-hold/40 bg-hold/10" },
  ESCALATE: { key: "verdict.ESCALATE", Icon: User, cls: "text-escalate border-escalate/40 bg-escalate/10" },
  DENY: { key: "verdict.DENY", Icon: ShieldAlert, cls: "text-deny border-deny/40 bg-deny/10" },
};

export function VerdictBadge({ verdict, className }: { verdict: Verdict; className?: string }) {
  const { t } = useT();
  const { key, Icon, cls } = META[verdict];
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold", cls, className)}>
      <Icon aria-hidden className="size-3.5" />
      {t(key)}
    </span>
  );
}
