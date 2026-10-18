"use client";

import { Check, Info, TriangleAlert } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";
import { cn } from "@/lib/utils";

type Tone = "ok" | "info" | "warn";
interface ToastItem { id: number; title: string; body?: string; tone: Tone }
const Ctx = createContext<(t: Omit<ToastItem, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-2), { ...t, id }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 6500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end md:px-6">
        {items.map((t) => {
          const Icon = t.tone === "ok" ? Check : t.tone === "warn" ? TriangleAlert : Info;
          return (
            <div key={t.id} role="status" className={cn("rise pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-card border border-border bg-surface p-3 shadow-card")}>
              <Icon aria-hidden className={cn("mt-0.5 size-5 shrink-0", t.tone === "ok" ? "text-allow" : t.tone === "warn" ? "text-hold" : "text-escalate")} />
              <div className="min-w-0 text-sm">
                <p className="font-semibold">{t.title}</p>
                {t.body ? <p className="mt-0.5 text-muted">{t.body}</p> : null}
              </div>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
