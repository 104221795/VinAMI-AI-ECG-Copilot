"use client";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <main className="vm-main">
          <div className="vm-state vm-state--error" role="alert">
            <h1>Application unavailable</h1>
            <p>The research workspace could not start safely.</p>
            <button className="vm-button" onClick={reset}>
              Retry
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
