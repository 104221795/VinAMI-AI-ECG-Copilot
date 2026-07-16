import "server-only";
import type { AuditEntryPageView } from "@web/entities/audit-entry/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadAuditWith } from "./data";

export function loadAudit(caseId: string): Promise<AuditEntryPageView> {
  return loadAuditWith(createServerApiClient(), caseId);
}
