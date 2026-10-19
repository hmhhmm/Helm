import { Card, Skeleton } from "@/components/ui/card";

/** Each screen opens with a one-line answer, then the evidence. */
export function ScreenHeader({ title, answer, children }: { title: string; answer: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{answer}</p>
      </div>
      {children}
    </div>
  );
}

export function CardsSkeleton({ n = 3 }: { n?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {Array.from({ length: n }).map((_, i) => (
        <Card key={i}>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-4 h-9 w-40" />
          <Skeleton className="mt-3 h-3 w-32" />
        </Card>
      ))}
    </div>
  );
}

export function BlockSkeleton({ h = 280 }: { h?: number }) {
  return <Card><Skeleton className="w-full" style={{ height: h }} /></Card>;
}

export function EmptyState({ title, body, children }: { title: string; body?: string; children?: React.ReactNode }) {
  return (
    <Card className="flex flex-col items-center gap-2 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {body && <p className="max-w-md text-sm text-muted">{body}</p>}
      {children}
    </Card>
  );
}
