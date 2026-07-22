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
      title="Không mở được không gian làm việc"
      description="Không thể hiển thị không gian lâm sàng một cách an toàn. Không có thao tác lâm sàng nào được ghi nhận."
      onRetry={reset}
    />
  );
}
