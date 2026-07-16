import type { Metadata } from "next";
import { TroponinWorkspace } from "@web/features/troponin/troponin-workspace";
import { loadTroponinWorkspace } from "@web/features/troponin/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Troponin Workspace" };
export default async function TroponinPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [caseValue, troponin] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadTroponinWorkspace(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="troponin" />
        <TroponinWorkspace caseId={caseId} initialValue={troponin} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
