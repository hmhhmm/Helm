"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

/** 44px-tall touch target around a 28px visual switch. */
export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn("group inline-flex h-11 w-14 shrink-0 cursor-pointer items-center justify-center rounded-lg data-[disabled]:opacity-50", className)}
      {...props}
    >
      <span className="relative inline-flex h-7 w-12 items-center rounded-full border border-border bg-border transition-colors duration-150 group-data-[state=checked]:bg-accent">
        <SwitchPrimitive.Thumb className="block size-5 translate-x-1 rounded-full bg-white shadow transition-transform duration-150 data-[state=checked]:translate-x-6" />
      </span>
    </SwitchPrimitive.Root>
  );
}
