import { ClinicalCard, TimelineItem } from "@vinami/ui";
import type { CaseWorkspaceView } from "@web/entities/clinical-case/model";
import type { TimelineEventView } from "@web/entities/timeline-event/model";
import {
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";

export function CaseOverview({
  value,
  timeline,
}: {
  value: CaseWorkspaceView;
  timeline: TimelineEventView[];
}) {
  const latest = [...timeline].sort((left, right) =>
    right.occurredAt.localeCompare(left.occurredAt),
  )[0];
  return (
    <div className="vm-section-stack">
      <section className="vm-summary-grid" aria-label="Case summary">
        <div className="vm-summary-block">
          <span>Current lifecycle state</span>
          <strong>{value.status.replaceAll("_", " ")}</strong>
          <p>Operational state, not a diagnosis</p>
        </div>
        <div className="vm-summary-block">
          <span>Clinical priority</span>
          <strong>{value.priority}</strong>
          <p>Recorded by the lifecycle command</p>
        </div>
        <div className="vm-summary-block">
          <span>Arrival</span>
          <strong>{formatRelative(value.arrivalAt)}</strong>
          <p>{formatTimestamp(value.arrivalAt)}</p>
        </div>
        <div className="vm-summary-block">
          <span>Encounter location</span>
          <strong>{value.location}</strong>
          <p>{value.encounterStatus} encounter</p>
        </div>
        <div className="vm-summary-block">
          <span>Case opened</span>
          <strong>{formatRelative(value.openedAt)}</strong>
          <p>{formatTimestamp(value.openedAt)}</p>
        </div>
        <div className="vm-summary-block">
          <span>Last persisted update</span>
          <strong>{formatRelative(value.updatedAt)}</strong>
          <p>Aggregate version {value.aggregateVersion}</p>
        </div>
      </section>
      <div className="vm-layout-split">
        <ClinicalCard title="Patient and encounter">
          <dl className="vm-definition-list">
            <dt>Patient reference</dt>
            <dd>{value.patientReference}</dd>
            <dt>Safe demographics</dt>
            <dd>{value.demographics}</dd>
            <dt>Reference system</dt>
            <dd>{value.patientReferenceSystem}</dd>
            <dt>Encounter reference</dt>
            <dd>{value.encounterReference}</dd>
            <dt>Location</dt>
            <dd>{value.location}</dd>
            <dt>Arrival time</dt>
            <dd>{formatTimestamp(value.arrivalAt)}</dd>
          </dl>
        </ClinicalCard>
        <ClinicalCard title="Latest lifecycle activity">
          {latest ? (
            <ol className="vm-timeline">
              <TimelineItem
                title={latest.title}
                timestamp={formatTimestamp(latest.occurredAt)}
                actor={
                  latest.actorId
                    ? shortReference(latest.actorId, "ACT")
                    : "System"
                }
                last
                detail={<p>Projection source: {latest.source}</p>}
              />
            </ol>
          ) : (
            <p>
              Lifecycle projections may still be processing. Use Timeline to
              refresh.
            </p>
          )}
        </ClinicalCard>
      </div>
      <ClinicalCard title="Case opening context">
        <p>{value.openingReason}</p>
      </ClinicalCard>
      <section className="vm-capabilities">
        <strong>Capabilities not yet enabled:</strong> serial troponin,
        reasoning, tasks, and alerts remain outside the verified R3 slice. No
        clinical data is inferred here.
      </section>
    </div>
  );
}
