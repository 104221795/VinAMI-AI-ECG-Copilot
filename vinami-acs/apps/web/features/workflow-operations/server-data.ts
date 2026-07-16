import "server-only";
import { createServerApiClient } from "@web/shared/api/client";
import { workflowOperationsSchema, type WorkflowOperationsView } from "./model";

export async function loadWorkflowOperations(
  caseId: string,
): Promise<WorkflowOperationsView> {
  return workflowOperationsSchema.parse(
    await createServerApiClient().getWorkflowOperationsWorkspace(caseId),
  );
}
