import type { VinamiApiClient } from "@vinami/api-client";
import type {
  TimelineEventPageView,
  TimelineEventView,
} from "@web/entities/timeline-event/model";
import { parseContract } from "@web/shared/api/parse";
import { timelineHistoryPageSchema } from "@web/shared/validation/contracts";

export async function loadTimelineWith(
  api: VinamiApiClient,
  caseId: string,
): Promise<TimelineEventPageView> {
  const page = parseContract(
    timelineHistoryPageSchema,
    await api.getTimelineHistory(caseId, { page: 1, page_size: 75 }),
  );
  return {
    items: page.items.map((event): TimelineEventView => ({
      id: event.timeline_event_id,
      title: event.title,
      eventType: event.event_type,
      occurredAt: event.occurred_at,
      recordedAt: event.recorded_at,
      source: event.source,
      actorId: event.actor_id,
      correlationId: event.correlation_id,
      causationId: event.causation_id,
      sourceRecordId: event.source_record_id,
      sourceRecordVersion: event.source_record_version,
      correctionStatus: event.correction_status,
      dataClassification: event.data_classification,
    })),
    page: page.page,
    pageSize: page.page_size,
    total: page.total,
  };
}
