"use client";

import { ErrorState } from "@vinami/ui";

export default function RouteError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorState
      title="Workspace unavailable"
      description="This clinical workspace could not be rendered safely. No clinical action was taken."
      onRetry={reset}
    />
  );
}
