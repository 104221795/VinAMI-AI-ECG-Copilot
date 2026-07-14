import Link from "next/link";
import { EmptyState } from "@vinami/ui";

export default function NotFound() {
  return (
    <>
      <EmptyState
        title="Page not found"
        description="The requested workspace is not part of the enabled R1 lifecycle slice."
      />
      <p style={{ textAlign: "center" }}>
        <Link href="/command-center">Return to Command Center</Link>
      </p>
    </>
  );
}
