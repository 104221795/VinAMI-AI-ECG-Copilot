import "server-only";
import { createServerApiClient } from "@web/shared/api/client";
import {
  clinicalReasoningWorkspaceSchema,
  type ClinicalReasoningWorkspaceView,
} from "./model";

export async function loadClinicalReasoningWorkspace(
  caseId: string,
): Promise<ClinicalReasoningWorkspaceView> {
  return clinicalReasoningWorkspaceSchema.parse(
    await createServerApiClient().getClinicalReasoningWorkspace(caseId),
  );
}
