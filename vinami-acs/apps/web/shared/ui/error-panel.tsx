"use client";

import { useRouter } from "next/navigation";
import { ErrorState } from "@vinami/ui";
import type { ErrorPresentation } from "@web/shared/errors/presentation";

export function ErrorPanel({
  presentation,
}: {
  presentation: ErrorPresentation;
}) {
  const router = useRouter();
  return (
    <ErrorState
      {...presentation}
      onRetry={presentation.retryable ? () => router.refresh() : undefined}
    />
  );
}
