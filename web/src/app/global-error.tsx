"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <div className="text-center">
          <h2 className="mb-2 text-lg font-semibold">Something went wrong</h2>
          <p className="mb-4 text-sm text-muted">{error.message}</p>
          <button
            type="button"
            onClick={reset}
            className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-card-hover"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
