import type { Metadata } from "next";
import { PageHeader } from "@vinami/ui";
import { AuditTable } from "@web/features/case-audit/audit-table";
import { loadAudit } from "@web/features/case-audit/server-data";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { presentError } from "@web/shared/errors/presentation";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Immutable Audit" };

export default async function AuditPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [workspace, entries] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadAudit(caseId),
    ]);
    return (
      <>
        <CaseWorkspaceHeader value={workspace} active="audit" />
        <PageHeader
          title="Immutable Audit"
          description="Read-only lifecycle audit with verified actor provenance. Credentials and secrets are never displayed."
        />
        <AuditTable entries={entries} />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
