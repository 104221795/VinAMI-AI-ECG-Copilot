import "server-only";
import type { TimelineEventView } from "@web/entities/timeline-event/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadTimelineWith } from "./data";

export function loadTimeline(caseId: string): Promise<TimelineEventView[]> {
  return loadTimelineWith(createServerApiClient(), caseId);
}
