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
  sourceRecordId: string | null;
  sourceRecordVersion: number | null;
  correctionStatus: string;
  dataClassification: string;
}

export interface TimelineEventPageView {
  items: TimelineEventView[];
  page: number;
  pageSize: number;
  total: number;
}
