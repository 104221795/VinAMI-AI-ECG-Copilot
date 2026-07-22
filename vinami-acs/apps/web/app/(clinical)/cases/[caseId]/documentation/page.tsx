import type { Metadata } from "next";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { ClinicalDocumentationWorkspace } from "@web/features/clinical-documentation/clinical-documentation-workspace";
import { loadClinicalDocumentation } from "@web/features/clinical-documentation/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Tiếp nhận và sinh hiệu" };

export default async function DocumentationPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [caseValue, documentation] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadClinicalDocumentation(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={caseValue} active="documentation" />
        <ClinicalDocumentationWorkspace caseId={caseId} value={documentation} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
