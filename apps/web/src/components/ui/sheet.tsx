"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

/** Right-hand drawer on desktop, full screen on phones. */
export function Sheet({
  open, onOpenChange, title, description, children, className, side = "right",
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  side?: "right" | "center";
}) {
  const { t } = useT();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-[fade_150ms_ease-out]" />
        <Dialog.Content
          className={cn(
            "fixed z-50 flex flex-col bg-bg shadow-card outline-none",
            side === "right"
              ? "inset-0 md:inset-y-0 md:left-auto md:right-0 md:w-[560px] md:border-l md:border-border data-[state=open]:animate-[slide_200ms_ease-out]"
              : "inset-0 m-auto h-fit max-h-[92dvh] w-full max-w-[440px] overflow-hidden rounded-card border border-border data-[state=open]:animate-[fade_150ms_ease-out] max-md:inset-x-0 max-md:bottom-0 max-md:top-auto max-md:m-0 max-md:max-w-none",
            className,
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-border bg-surface px-4 py-3 md:px-5">
            <div className="min-w-0">
              <Dialog.Title className="truncate text-lg font-bold tracking-tight">{title}</Dialog.Title>
              {description ? <Dialog.Description className="mt-0.5 text-sm text-muted">{description}</Dialog.Description> : <Dialog.Description className="sr-only">{title}</Dialog.Description>}
            </div>
            <Dialog.Close
              aria-label={t("common.close")}
              className="inline-flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-lg hover:bg-bg"
            >
              <X className="size-5" />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
