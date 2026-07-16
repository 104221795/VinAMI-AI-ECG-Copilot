import "server-only";
import { createServerApiClient } from "@web/shared/api/client";
import { loadCompleteCaseWorkspaceWith } from "./data";

export function loadCompleteCaseWorkspace(caseId: string) {
  return loadCompleteCaseWorkspaceWith(createServerApiClient(), caseId);
}
