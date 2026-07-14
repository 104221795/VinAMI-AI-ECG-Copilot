import type { VinamiApiClient } from "@vinami/api-client";
import type { TimelineEventView } from "@web/entities/timeline-event/model";
import { parseContract } from "@web/shared/api/parse";
import { timelineSchema } from "@web/shared/validation/contracts";

export async function loadTimelineWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<TimelineEventView[]> {
  return parseContract(timelineSchema, await api.getTimeline(caseId)).map(
    (event) => ({
      id: event.timeline_event_id,
      title: event.title,
      eventType: event.event_type,
      occurredAt: event.occurred_at,
      recordedAt: event.recorded_at,
      source: event.source,
      actorId: event.actor_id,
      correlationId: event.correlation_id,
      causationId: event.causation_id,
    }),
  );
}
