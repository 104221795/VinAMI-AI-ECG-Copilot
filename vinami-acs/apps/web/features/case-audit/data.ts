import type { VinamiApiClient } from "@vinami/api-client";
import type {
  AuditEntryPageView,
  AuditEntryView,
} from "@web/entities/audit-entry/model";
import { parseContract } from "@web/shared/api/parse";
import { shortReference } from "@web/shared/formatting";
import { auditHistoryPageSchema } from "@web/shared/validation/contracts";

export async function loadAuditWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<AuditEntryPageView> {
  const page = parseContract(
    auditHistoryPageSchema,
    await api.getAuditHistory(caseId, { page: 1, page_size: 75 }),
  );
  return {
    items: page.items.map((entry): AuditEntryView => ({
      id: entry.audit_id,
      actor: entry.actor_id ? shortReference(entry.actor_id, "ACT") : "System",
      actorRole: entry.actor_role ?? "Not supplied",
      actorRoles: entry.actor_roles,
      action: entry.action,
      resource: entry.resource_type,
      resourceId: entry.resource_id,
      outcome: entry.outcome,
      priorVersion: entry.prior_version,
      resultingVersion: entry.resulting_version,
      requestSource: entry.request_source,
      timestamp: entry.recorded_at,
      reason: entry.reason,
      correlationId: entry.correlation_id,
      causationId: entry.causation_id,
      identityProvider: entry.identity_provider,
      authenticationMethod: entry.authentication_method,
      idempotencyKey: entry.idempotency_key,
      authorizationResult: entry.authorization_result,
      correctionStatus: entry.correction_status,
      sourceRecordVersion: entry.source_record_version,
    })),
    page: page.page,
    pageSize: page.page_size,
    total: page.total,
  };
}
