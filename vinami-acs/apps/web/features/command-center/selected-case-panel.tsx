"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Button,
  ClinicalCard,
  EmptyState,
  LoadingSkeleton,
  PriorityBadge,
  StatusBadge,
  TechnicalDetailsDisclosure,
  TimelineItem,
} from "@vinami/ui";
import type { CaseQueueRowView } from "@web/entities/clinical-case/model";
import { loadTimelineWith } from "@web/features/case-timeline/data";
import { createBrowserApiClient } from "@web/shared/api/browser";
import {
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";

export function SelectedCasePanel({
  row,
  onClear,
  referenceTime,
}: {
  row?: CaseQueueRowView;
  onClear: () => void;
  referenceTime: string;
}) {
  const now = new Date(referenceTime).getTime();
  const timeline = useQuery({
    queryKey: ["timeline-preview", row?.caseId],
    queryFn: () => loadTimelineWith(createBrowserApiClient(), row!.caseId),
    enabled: Boolean(row),
    staleTime: 10_000,
  });
  if (!row)
    return (
      <ClinicalCard className="vm-selected-panel">
        <EmptyState
          title="No case selected"
          description="Select a queue row to review its lifecycle context."
        />
      </ClinicalCard>
    );
  return (
    <ClinicalCard
      title="Selected case"
      className="vm-selected-panel"
      action={<Button onClick={onClear}>Clear</Button>}
    >
      <div className="vm-case-header">
        <PriorityBadge priority={row.priority} />
        <StatusBadge status={row.status} />
      </div>
      <dl className="vm-definition-list">
        <dt>Patient</dt>
        <dd>
          {row.patientReference}
          <br />
          <small>{row.demographics}</small>
        </dd>
        <dt>Case</dt>
        <dd>{row.caseReference}</dd>
        <dt>Encounter</dt>
        <dd>{row.encounterReference}</dd>
        <dt>Location</dt>
        <dd>{row.location}</dd>
        <dt>Opened</dt>
        <dd title={formatTimestamp(row.openedAt)}>
          {formatRelative(row.openedAt, now)}
        </dd>
        <dt>Updated</dt>
        <dd title={formatTimestamp(row.updatedAt)}>
          {formatRelative(row.updatedAt, now)}
        </dd>
      </dl>
      <h3>Recent lifecycle events</h3>
      {timeline.isLoading && (
        <LoadingSkeleton lines={3} label="Loading recent lifecycle events" />
      )}
      {timeline.data && timeline.data.length > 0 && (
        <ol className="vm-timeline">
          {timeline.data
            .slice(-3)
            .reverse()
            .map((event, index, items) => (
              <TimelineItem
                key={event.id}
                title={event.title}
                timestamp={formatRelative(event.occurredAt, now)}
                actor={
                  event.actorId
                    ? shortReference(event.actorId, "ACT")
                    : "System"
                }
                last={index === items.length - 1}
              />
            ))}
        </ol>
      )}
      {timeline.data?.length === 0 && (
        <p>
          Lifecycle projection is still processing. Refresh after the worker
          publishes the events.
        </p>
      )}
      {timeline.isError && (
        <p>
          Recent events are still processing or unavailable. Open Timeline to
          retry.
        </p>
      )}
      <Link
        href={`/cases/${row.caseId}`}
        className="vm-button vm-button--primary"
      >
        Open case workspace
      </Link>
      <TechnicalDetailsDisclosure>
        <code>{row.caseId}</code>
      </TechnicalDetailsDisclosure>
    </ClinicalCard>
  );
}
