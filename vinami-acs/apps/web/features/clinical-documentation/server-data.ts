import "server-only";
import type { ClinicalDocumentationView } from "@web/entities/clinical-documentation/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadClinicalDocumentationWith } from "./data";

export function loadClinicalDocumentation(
  caseId: string,
): Promise<ClinicalDocumentationView> {
  return loadClinicalDocumentationWith(createServerApiClient(), caseId);
}
