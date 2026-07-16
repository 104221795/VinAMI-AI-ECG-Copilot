import type { VinamiApiClient } from "@vinami/api-client";
import { parseContract } from "@web/shared/api/parse";
import {
  completeCaseWorkspaceSchema,
  type CompleteCaseWorkspaceView,
} from "./model";

export async function loadCompleteCaseWorkspaceWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<CompleteCaseWorkspaceView> {
  return parseContract(
    completeCaseWorkspaceSchema,
    await api.getCompleteCaseWorkspace(caseId),
  );
}
