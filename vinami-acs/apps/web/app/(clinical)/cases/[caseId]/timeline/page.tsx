import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import { TimelineView } from "@web/features/case-timeline/timeline-view";
import { loadTimeline } from "@web/features/case-timeline/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Lifecycle Timeline" };

export default async function TimelinePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [workspace, events] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadTimeline(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={workspace} active="timeline" />
        <PageHeader
          title="Lifecycle Timeline"
          description="Persisted event projections from the transactional outbox. Newly committed events may appear after the worker processes them."
        />
        <TimelineView events={events} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
