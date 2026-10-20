"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { I18nProvider } from "@/i18n";
import { LoginDialog } from "./login-dialog";
import { OverlayProvider } from "./overlays";
import { Shell } from "./shell";
import { ToastProvider } from "./ui/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } }));
  return (
    <QueryClientProvider client={qc}>
      <I18nProvider>
        <ToastProvider>
          <OverlayProvider>
            <Shell>{children}</Shell>
            <LoginDialog />
          </OverlayProvider>
        </ToastProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
