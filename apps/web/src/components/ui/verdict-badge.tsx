import { Check, Clock, ShieldAlert, User } from "lucide-react";
import { cn } from "@/lib/utils";

export type Verdict = "ALLOW" | "HOLD" | "ESCALATE" | "DENY";

// Status is never colour alone: each verdict has an icon and a word.
const META = {
  ALLOW: { label: "Released", Icon: Check, cls: "text-allow border-allow/40 bg-allow/10" },
  HOLD: { label: "Waiting for cash", Icon: Clock, cls: "text-hold border-hold/40 bg-hold/10" },
  ESCALATE: { label: "Needs you", Icon: User, cls: "text-escalate border-escalate/40 bg-escalate/10" },
  DENY: { label: "Blocked by rule", Icon: ShieldAlert, cls: "text-deny border-deny/40 bg-deny/10" },
} as const;

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { label, Icon, cls } = META[verdict];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold", cls)}>
      <Icon aria-hidden className="size-3.5" />
      {label}
    </span>
  );
}
