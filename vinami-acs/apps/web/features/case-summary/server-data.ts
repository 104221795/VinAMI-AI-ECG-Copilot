import "server-only";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadCaseWorkspaceWith } from "./data";

export function loadCaseWorkspace(caseId: string): Promise<CaseWorkspaceView> {
  return loadCaseWorkspaceWith(createServerApiClient(), caseId);
}
