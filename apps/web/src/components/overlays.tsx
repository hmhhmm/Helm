"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { ApprovalCard } from "./approval-card";
import { CommandPalette } from "./command-palette";
import { DecisionSheet } from "./decision-sheet";
import { SimulatorDrawer } from "./simulator-drawer";
import { Sheet } from "./ui/sheet";
import { useT } from "@/i18n";

interface Overlays {
  openDecision: (id: string, opts?: { tryToday?: boolean }) => void;
  openApproval: (id: string) => void;
  openSimulator: () => void;
  openPalette: () => void;
}
const Ctx = createContext<Overlays | null>(null);
export const useOverlays = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useOverlays outside provider");
  return c;
};

export function OverlayProvider({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  const [decision, setDecision] = useState<{ id: string; tryToday?: boolean } | null>(null);
  const [approval, setApproval] = useState<string | null>(null);
  const [sim, setSim] = useState(false);
  const [palette, setPalette] = useState(false);
  const value: Overlays = {
    openDecision: useCallback((id, opts) => setDecision({ id, tryToday: opts?.tryToday }), []),
    openApproval: useCallback((id) => setApproval(id), []),
    openSimulator: useCallback(() => setSim(true), []),
    openPalette: useCallback(() => setPalette(true), []),
  };
  return (
    <Ctx.Provider value={value}>
      {children}
      <DecisionSheet id={decision?.id ?? null} tryToday={decision?.tryToday} onClose={() => setDecision(null)} />
      <Sheet open={!!approval} onOpenChange={(o) => !o && setApproval(null)} title={t("approval.title")} side="center">
        {approval && <ApprovalCard id={approval} />}
      </Sheet>
      <SimulatorDrawer open={sim} onOpenChange={setSim} />
      <CommandPalette open={palette} onOpenChange={setPalette} />
    </Ctx.Provider>
  );
}
