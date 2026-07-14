import "server-only";
import type { CaseListQuery } from "@vinami/api-client";
import type { CaseQueueView } from "@web/entities/clinical-case/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadCaseQueueWith } from "./data";

export function loadCaseQueue(query: CaseListQuery): Promise<CaseQueueView> {
  return loadCaseQueueWith(createServerApiClient(), query);
}
