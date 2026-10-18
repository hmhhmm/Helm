import { Card, Skeleton } from "@/components/ui/card";

/** Each screen opens with a one-line answer, then the evidence. */
export function ScreenHeader({ title, answer }: { title: string; answer: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-1 text-muted">{answer}</p>
    </div>
  );
}

export function ScreenSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-3" aria-busy="true" aria-label="Loading">
      {[0, 1, 2].map((i) => (
        <Card key={i}>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-4 h-9 w-40" />
          <Skeleton className="mt-3 h-3 w-32" />
        </Card>
      ))}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <Card className="text-center text-muted">
      <p>{message}</p>
    </Card>
  );
}
