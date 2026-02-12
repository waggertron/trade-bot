"use client";

import { cn } from "@/lib/formatters";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-border/50", className)} />;
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <Skeleton className="mb-3 h-3 w-20" />
      <Skeleton className="mb-2 h-8 w-32" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      <Skeleton className="h-8 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = "h-64" }: { height?: string }) {
  return <Skeleton className={cn("w-full", height)} />;
}
