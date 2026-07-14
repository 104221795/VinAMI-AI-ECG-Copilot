import type { Metadata } from "next";
import { Badge } from "@vinami/ui";
import { CaseOverview } from "@web/features/case-summary/case-overview";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { ClinicalDocumentationWorkspace } from "@web/features/clinical-documentation/clinical-documentation-workspace";
import { loadClinicalDocumentation } from "@web/features/clinical-documentation/server-data";
import { loadTimeline } from "@web/features/case-timeline/server-data";
import { ECGWorkspace } from "@web/features/ecg/ecg-workspace";
import { loadECGWorkspace } from "@web/features/ecg/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Clinical Case" };

export default async function CaseWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [value, documentation, timeline, ecg] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadClinicalDocumentation(caseId),
      loadTimeline(caseId).catch(() => []),
      loadECGWorkspace(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={value} />
        <div style={{ marginBottom: 12 }}>
          <Badge tone="warning">Research-use prototype</Badge>
        </div>
        <CaseOverview value={value} timeline={timeline} />
        <ClinicalDocumentationWorkspace caseId={caseId} value={documentation} />
        <ECGWorkspace
          caseId={caseId}
          caseVersion={value.aggregateVersion}
          initialValue={ecg}
        />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
