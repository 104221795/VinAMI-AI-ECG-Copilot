import type { VinamiApiClient } from "@vinami/api-client";
import type { AuditEntryView } from "@web/entities/audit-entry/model";
import { parseContract } from "@web/shared/api/parse";
import { shortReference } from "@web/shared/formatting";
import { auditSchema } from "@web/shared/validation/contracts";

export async function loadAuditWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<AuditEntryView[]> {
  return parseContract(auditSchema, await api.getAudit(caseId)).map(
    (entry) => ({
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
    }),
  );
}
