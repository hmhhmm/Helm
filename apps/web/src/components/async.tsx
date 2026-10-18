"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { useT } from "@/i18n";
import { API_URL } from "@/lib/api";
import { Button } from "./ui/button";
import { Card } from "./ui/card";

/** Loading skeleton, readable error with retry, then the content. */
export function Async<T>({
  q, skeleton, children,
}: {
  q: UseQueryResult<T>;
  skeleton: React.ReactNode;
  children: (data: T) => React.ReactNode;
}) {
  const { t } = useT();
  if (q.isPending) return <div aria-busy="true" aria-label={t("common.loading")}>{skeleton}</div>;
  if (q.isError)
    return (
      <Card className="flex flex-col items-start gap-3" role="alert">
        <div className="flex items-center gap-2 font-semibold">
          <TriangleAlert aria-hidden className="size-5 text-hold" />
          {t("error.title")}
        </div>
        <p className="text-sm text-muted">{t("error.body", { url: API_URL })}</p>
        <p className="num rounded bg-bg px-2 py-1 text-xs text-muted">{(q.error as Error).message}</p>
        <Button variant="secondary" onClick={() => q.refetch()}>{t("common.retry")}</Button>
      </Card>
    );
  return <>{children(q.data)}</>;
}
