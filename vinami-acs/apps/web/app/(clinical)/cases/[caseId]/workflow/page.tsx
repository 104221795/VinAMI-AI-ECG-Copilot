import type { Metadata } from "next";
import { loadCaseWorkspace } from "@web/features/case-summary/server-data";
import { loadClinicalReasoningWorkspace } from "@web/features/clinical-reasoning/server-data";
import { loadIdentity } from "@web/features/identity-session/data";
import { WorkflowOperationsWorkspace } from "@web/features/workflow-operations/workflow-operations-workspace";
import { loadWorkflowOperations } from "@web/features/workflow-operations/server-data";
import { presentError } from "@web/shared/errors/presentation";
import { ErrorPanel } from "@web/shared/ui/error-panel";
import { CaseWorkspaceHeader } from "@web/widgets/case-workspace-header/case-workspace-header";

export const metadata: Metadata = { title: "Quy trình, công việc và cảnh báo" };

export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  try {
    const [caseValue, workflow, reasoning, identity] = await Promise.all([
      loadCaseWorkspace(caseId),
      loadWorkflowOperations(caseId),
      loadClinicalReasoningWorkspace(caseId),
      loadIdentity(),
    ]);
    return (
      <>
        <CaseWorkspaceHeader
          value={caseValue}
          active="workflow"
          workflowStatus={workflow.workflow.state}
        />
        <WorkflowOperationsWorkspace
          caseId={caseId}
          actorId={identity.actorId}
          initialValue={workflow}
          decisions={reasoning.decisions}
        />
      </>
    );
  } catch (error) {
    return <ErrorPanel presentation={presentError(error)} />;
  }
}
