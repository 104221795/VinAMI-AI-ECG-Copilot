import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import { loadSystemHealth } from "@web/features/system-health/data";
import { SystemHealth } from "@web/features/system-health/system-health";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";

export const metadata: Metadata = { title: "System Health" };

export default async function SystemHealthPage() {
  try {
    const value = await loadSystemHealth();
    return (
      <>
        <PageHeader
          eyebrow="Technical operations"
          title="System Health"
          description="Dependency readiness is separated from the clinical queue and contains no patient information."
        />
        <SystemHealth value={value} />
      </>
    );
  } catch (error) {
    return (
      <>
        <PageHeader eyebrow="Technical operations" title="System Health" />
        <ErrorPanel presentation={presentError(error)} />
      </>
    );
  }
}
