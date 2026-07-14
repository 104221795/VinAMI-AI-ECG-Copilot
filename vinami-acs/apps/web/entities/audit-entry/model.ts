export interface AuditEntryView {
  id: string;
  actor: string;
  actorRole: string;
  actorRoles: string[];
  action: string;
  resource: string;
  resourceId: string;
  outcome: string;
  priorVersion: number | null;
  resultingVersion: number | null;
  requestSource: string;
  timestamp: string;
  reason: string | null;
  correlationId: string;
  causationId: string | null;
  identityProvider: string | null;
  authenticationMethod: string | null;
}
