import "server-only";
import { createServerApiClient } from "@web/shared/api/client";
import { loadModelProvenanceWith, loadOutcomeHistoryWith } from "./data";
import type { ModelProvenanceView, OutcomeHistoryView } from "./model";

export async function loadOutcomeHistory(
  caseId: string,
): Promise<OutcomeHistoryView> {
  return loadOutcomeHistoryWith(createServerApiClient(), caseId);
}

export async function loadModelProvenance(
  caseId: string,
): Promise<ModelProvenanceView[]> {
  return loadModelProvenanceWith(createServerApiClient(), caseId);
}
