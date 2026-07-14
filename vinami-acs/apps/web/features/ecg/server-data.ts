import "server-only";
import type { ECGWorkspaceView } from "@web/entities/ecg/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadECGWorkspaceWith } from "./data";

export function loadECGWorkspace(caseId: string): Promise<ECGWorkspaceView> {
  return loadECGWorkspaceWith(createServerApiClient(), caseId);
}
