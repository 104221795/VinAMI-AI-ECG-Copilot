export interface TimelineEventView {
  id: string;
  title: string;
  eventType: string;
  occurredAt: string;
  recordedAt: string;
  source: string;
  actorId: string | null;
  correlationId: string;
  causationId: string | null;
}
