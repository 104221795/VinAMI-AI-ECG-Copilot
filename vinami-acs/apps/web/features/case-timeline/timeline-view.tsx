"use client";

import { useMemo, useState } from "react";
import {
  EmptyState,
  StatusBadge,
  TechnicalDetailsDisclosure,
  TimelineItem,
} from "@vinami/ui";
import type { TimelineEventPageView } from "@web/entities/timeline-event/model";
import { formatTimestamp, shortReference } from "@web/shared/formatting";

export function TimelineView({ value }: { value: TimelineEventPageView }) {
  const [order, setOrder] = useState<"newest" | "oldest">("newest");
  const [status, setStatus] = useState("all");
  const events = value.items;
  const ordered = useMemo(
    () =>
      events
        .filter((event) => status === "all" || event.correctionStatus === status)
        .sort((left, right) =>
          order === "newest"
            ? right.occurredAt.localeCompare(left.occurredAt)
            : left.occurredAt.localeCompare(right.occurredAt),
        ),
    [events, order, status],
  );
  if (!events.length)
    return (
      <EmptyState
        title="Timeline projection pending"
        description="Committed lifecycle events may still be processing. Refresh after the worker completes the projection."
      />
    );
  return (
    <section className="vm-card">
      <header className="vm-card__header">
        <h2>Persisted lifecycle events</h2>
        <label className="vm-field">
          <span>Order</span>
          <select
            value={order}
            onChange={(event) =>
              setOrder(event.target.value as "newest" | "oldest")
            }
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </label>
        <label className="vm-field">
          <span>History state</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All</option>
            <option value="original">Original</option>
            <option value="correction">Correction</option>
            <option value="revocation">Revocation</option>
          </select>
        </label>
      </header>
      <div className="vm-card__body">
        <p className="vm-muted">
          Showing {ordered.length} of {value.total} backend-projected events.
          Timeline rows are created from persisted backend events, not frontend
          state.
        </p>
        <ol className="vm-timeline">
          {ordered.map((event, index) => (
            <TimelineItem
              key={event.id}
              title={event.title}
              timestamp={formatTimestamp(event.occurredAt)}
              actor={
                event.actorId ? shortReference(event.actorId, "ACT") : "System"
              }
              last={index === ordered.length - 1}
              detail={
                <TechnicalDetailsDisclosure>
                  <dl>
                    <dt>History state</dt>
                    <dd>
                      <StatusBadge status={event.correctionStatus} />
                    </dd>
                    <dt>Event type</dt>
                    <dd>{event.eventType}</dd>
                    <dt>Recorded</dt>
                    <dd>{formatTimestamp(event.recordedAt)}</dd>
                    <dt>Source record</dt>
                    <dd>
                      <code>{event.sourceRecordId ?? "Not supplied"}</code>
                    </dd>
                    <dt>Source version</dt>
                    <dd>{event.sourceRecordVersion ?? "Not supplied"}</dd>
                    <dt>Data class</dt>
                    <dd>{event.dataClassification}</dd>
                    <dt>Source</dt>
                    <dd>{event.source}</dd>
                    <dt>Correlation</dt>
                    <dd>
                      <code>{event.correlationId}</code>
                    </dd>
                    <dt>Causation</dt>
                    <dd>
                      <code>{event.causationId ?? "None"}</code>
                    </dd>
                  </dl>
                </TechnicalDetailsDisclosure>
              }
            />
          ))}
        </ol>
      </div>
    </section>
  );
}
