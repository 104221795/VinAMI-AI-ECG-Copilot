import type { Metadata } from "next";
import { ECGWorkspace } from "@web/features/ecg/ecg-workspace";
import { loadECGWorkspace } from "@web/features/ecg/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "ECG Workspace" };

export default async function ECGWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [caseValue, ecg] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadECGWorkspace(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="ecg" />
        <ECGWorkspace caseId={caseId} initialValue={ecg} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
