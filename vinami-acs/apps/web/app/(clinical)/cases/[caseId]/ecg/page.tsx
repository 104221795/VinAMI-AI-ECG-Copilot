import type { Metadata } from "next";
import { ECGWorkspace } from "@web/features/ecg/ecg-workspace";
import { loadECGWorkspace } from "@web/features/ecg/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Không gian ECG" };

export default async function ECGWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  let caseValue: Awaited<ReturnType<typeof loadCaseWorkspace>>;
  try {
    caseValue = await loadCaseWorkspace(caseId);
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }

  try {
    const ecg = await loadECGWorkspace(caseId);
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="ecg" />
        <ECGWorkspace caseId={caseId} initialValue={ecg} />
      </>
    );
  } catch (error) {
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="ecg" />
        <ErrorPanel presentation={presentError(error)} />
      </>
    );
  }
}
