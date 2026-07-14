import "server-only";
import type { AuditEntryView } from "@web/entities/audit-entry/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadAuditWith } from "./data";

export function loadAudit(caseId: string): Promise<AuditEntryView[]> {
  return loadAuditWith(createServerApiClient(), caseId);
}
