import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import { CaseHistoryPanel } from "@web/features/case-history/case-history-panel";
import {
  loadModelProvenance,
  loadOutcomeHistory,
} from "@web/features/case-history/server-data";
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
    const [workspace, timeline, outcomes, provenance] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadTimeline(caseId),
      loadOutcomeHistory(caseId),
      loadModelProvenance(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={workspace} active="timeline" />
        <PageHeader
          title="Timeline, Outcome and Learning Record"
          description="Consolidated backend Timeline, physician-authored outcome revisions, model provenance and research-use export."
        />
        <TimelineView value={timeline} />
        <CaseHistoryPanel
          caseId={caseId}
          initialOutcomes={outcomes}
          initialProvenance={provenance}
        />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
