import "server-only";
import type { TimelineEventPageView } from "@web/entities/timeline-event/model";
import { createServerApiClient } from "@web/shared/api/client";
import { loadTimelineWith } from "./data";

export function loadTimeline(caseId: string): Promise<TimelineEventPageView> {
  return loadTimelineWith(createServerApiClient(), caseId);
}
