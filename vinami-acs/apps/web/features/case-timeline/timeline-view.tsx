"use client";

import { useMemo, useState } from "react";
import {
  EmptyState,
  TechnicalDetailsDisclosure,
  TimelineItem,
} from "@vinami/ui";
import type { TimelineEventView } from "@web/entities/timeline-event/model";
import { formatTimestamp, shortReference } from "@web/shared/formatting";

export function TimelineView({ events }: { events: TimelineEventView[] }) {
  const [order, setOrder] = useState<"newest" | "oldest">("newest");
  const ordered = useMemo(
    () =>
      [...events].sort((left, right) =>
        order === "newest"
          ? right.occurredAt.localeCompare(left.occurredAt)
          : left.occurredAt.localeCompare(right.occurredAt),
      ),
    [events, order],
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
      </header>
      <div className="vm-card__body">
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
                    <dt>Event type</dt>
                    <dd>{event.eventType}</dd>
                    <dt>Recorded</dt>
                    <dd>{formatTimestamp(event.recordedAt)}</dd>
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
