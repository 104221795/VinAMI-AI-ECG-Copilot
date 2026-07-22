import type { Metadata } from "next";
import { ClinicalReasoningWorkspace } from "@web/features/clinical-reasoning/clinical-reasoning-workspace";
import { loadClinicalReasoningWorkspace } from "@web/features/clinical-reasoning/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Tổng hợp lâm sàng" };

export default async function ClinicalReasoningPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [caseValue, reasoning] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadClinicalReasoningWorkspace(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="clinical-reasoning" />
        <ClinicalReasoningWorkspace caseId={caseId} initialValue={reasoning} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
