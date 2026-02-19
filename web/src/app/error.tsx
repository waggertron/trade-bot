"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="text-center">
        <h2 className="mb-2 text-lg font-semibold text-foreground">Something went wrong</h2>
        <p className="mb-4 text-sm text-muted">{error.message}</p>
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-card-hover"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
