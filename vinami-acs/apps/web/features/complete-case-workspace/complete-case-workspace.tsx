"use client";

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { AlertTriangle, Clock3, RefreshCw } from "lucide-react";
import Link from "next/link";
import {
  ErrorState,
  LoadingSkeleton,
  OfflineState,
  StaleDataBanner,
} from "@vinami/ui";
import { createBrowserApiClient } from "@web/shared/api/browser";
import { presentError } from "@web/shared/errors/presentation";
import { formatTimestamp, safeDemographics } from "@web/shared/formatting";
import { useConnectivity } from "@web/shared/hooks/use-connectivity";
import { loadCompleteCaseWorkspaceWith } from "./data";
import type { CompleteCaseWorkspaceView } from "./model";

const text = (value: unknown, fallback = "Not recorded") =>
  typeof value === "string" && value.length ? value : fallback;
const number = (value: unknown) => (typeof value === "number" ? value : 0);
const list = (value: unknown) => (Array.isArray(value) ? value : []);

export function CompleteCaseWorkspace({
  caseId,
  initialValue,
}: {
  caseId: string;
  initialValue: CompleteCaseWorkspaceView;
}) {
  const online = useConnectivity();
  const query = useQuery({
    queryKey: ["r8-complete-case-workspace", caseId],
    queryFn: () =>
      loadCompleteCaseWorkspaceWith(createBrowserApiClient(), caseId),
    initialData: initialValue,
    staleTime: 20_000,
    refetchInterval: 30_000,
  });
  if (!online && !query.data)
    return <OfflineState onRetry={() => query.refetch()} />;
  if (query.isLoading) return <LoadingSkeleton lines={12} />;
  if (query.isError) {
    const error = presentError(query.error);
    return (
      <ErrorState
        {...error}
        onRetry={error.retryable ? () => query.refetch() : undefined}
      />
    );
  }
  const value = query.data;
  if (!value) return null;
  const stale =
    !online || Date.now() - new Date(value.evaluated_at).getTime() > 60_000;
  const latestTroponin = value.troponin.latest_result as Record<
    string,
    unknown
  > | null;
  const latestDelta = value.troponin.latest_delta as Record<
    string,
    unknown
  > | null;
  const interpretation = value.ecg?.physician_interpretation as Record<
    string,
    unknown
  > | null;
  const analysis = value.ecg?.analysis as Record<string, unknown> | null;

  return (
    <main
      className="vm-case-workspace"
      aria-label="Complete clinical case workspace"
    >
      {stale && (
        <StaleDataBanner updatedLabel={formatTimestamp(value.evaluated_at)} />
      )}
      <header className="vm-case-workspace__header">
        <div>
          <p className="vm-eyebrow">Suspected ACS clinical case</p>
          <h1>{value.patient_name ?? value.patient_reference}</h1>
          <p>
            {value.patient_reference} ·{" "}
            {safeDemographics(value.age_band, value.sex_at_birth)} ·{" "}
            {value.location}
          </p>
        </div>
        <div
          className="vm-case-workspace__status"
          aria-label="Case status and update"
        >
          <strong>{value.case_status.replaceAll("_", " ")}</strong>
          <span>Priority {value.case_priority}</span>
          <span>Updated {formatTimestamp(value.last_updated_at)}</span>
          <button
            className="vm-button vm-button--secondary"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw size={15} aria-hidden />{" "}
            {query.isFetching ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </header>

      <nav
        className="vm-case-workspace__nav"
        aria-label="Case workspace navigation"
      >
        <Link href={`/cases/${caseId}/ecg`}>ECG</Link>
        <Link href={`/cases/${caseId}/troponin`}>Troponin</Link>
        <Link href={`/cases/${caseId}/clinical-reasoning`}>
          Clinical Reasoning
        </Link>
        <Link href={`/cases/${caseId}/workflow`}>Workflow</Link>
        <Link href={`/cases/${caseId}/timeline`}>Timeline</Link>
        <Link href={`/cases/${caseId}/audit`}>Audit</Link>
      </nav>

      <section
        className={`vm-evidence-banner vm-evidence-banner--${value.evidence_status}`}
        aria-labelledby="evidence-attention-title"
      >
        <AlertTriangle size={18} aria-hidden />
        <div>
          <h2 id="evidence-attention-title">Evidence attention</h2>
          <p>
            Missing:{" "}
            {value.missing_evidence.length
              ? value.missing_evidence.join(", ")
              : "none recorded"}
            . Stale:{" "}
            {value.stale_evidence.length
              ? value.stale_evidence.join(", ")
              : "none recorded"}
            .
          </p>
          {value.technical_limits.map((item) => (
            <p key={item}>{item}</p>
          ))}
          <small>Missing or unknown evidence is not negative evidence.</small>
        </div>
      </section>

      <div className="vm-case-workspace__grid">
        <Panel
          title="Triage and latest vitals"
          ownerLabel="Triage module owned evidence"
        >
          {value.triage ? (
            <>
              <Fact
                label="Chief complaint"
                value={text(value.triage.chief_complaint)}
              />
              <Fact
                label="Symptoms"
                value={text(value.triage.symptom_description)}
              />
              <Fact
                label="Clinical time"
                value={formatTimestamp(text(value.triage.occurred_at))}
              />
              <Source value={value.triage} idKey="assessment_id" />
            </>
          ) : (
            <Empty label="No current triage record" />
          )}
          <div className="vm-vital-compact">
            {value.vitals ? (
              list(value.vitals.measurements).map((item, index) => {
                const measurement = item as Record<string, unknown>;
                return (
                  <span key={`${text(measurement.kind)}-${index}`}>
                    <strong>{text(measurement.value, "—")}</strong>{" "}
                    {text(measurement.unit, "")}
                    <small>{text(measurement.kind)}</small>
                  </span>
                );
              })
            ) : (
              <Empty label="No current vital set" />
            )}
          </div>
        </Panel>

        <Panel
          title="ECG evidence"
          link={`/cases/${caseId}/ecg`}
          linkLabel="Open ECG workspace"
        >
          {value.ecg ? (
            <>
              <Fact label="Study" value={text(value.ecg.study_reference)} />
              <Fact
                label="Technical quality"
                value={text(value.ecg.quality_status)}
              />
              <Fact
                label="Acquired"
                value={formatTimestamp(text(value.ecg.acquisition_at))}
              />
              <Fact
                label="AI-supported finding"
                value={
                  analysis
                    ? `${text(analysis.status)} · ${text(analysis.model_name)} ${text(analysis.model_version, "")}`
                    : "No model result"
                }
              />
              <Fact
                label="Physician interpretation"
                value={
                  interpretation
                    ? text(interpretation.structured_interpretation)
                    : "Physician review not recorded"
                }
              />
              <Source value={value.ecg} idKey="study_id" />
              <small>
                Model output is decision support, not a diagnosis or clinical
                probability.
              </small>
            </>
          ) : (
            <Empty label="No ECG evidence recorded" />
          )}
        </Panel>

        <Panel
          title="Serial troponin"
          link={`/cases/${caseId}/troponin`}
          linkLabel="Open Troponin workspace"
        >
          {latestTroponin ? (
            <>
              <Fact
                label="Latest result"
                value={`${text(latestTroponin.value)} ${text(latestTroponin.unit, "")}`}
              />
              <Fact label="Assay" value={text(latestTroponin.assay_name)} />
              <Fact
                label="Specimen time"
                value={formatTimestamp(
                  text(latestTroponin.specimen_collected_at),
                )}
              />
              <Fact
                label="Effective results"
                value={String(number(value.troponin.result_count))}
              />
              <Fact
                label="Latest owner-calculated delta"
                value={
                  latestDelta
                    ? `${text(latestDelta.absolute_change)} ${text(latestDelta.unit, "")} · ${text(latestDelta.compatibility_status)}`
                    : "Awaiting serial compatible result"
                }
              />
              <Source value={latestTroponin} idKey="result_id" />
            </>
          ) : (
            <Empty label="No effective troponin result" />
          )}
        </Panel>

        <Panel
          title="Clinical reasoning and physician authority"
          link={`/cases/${caseId}/clinical-reasoning`}
          linkLabel="Open Clinical Reasoning"
        >
          {value.physician_assessment ? (
            <>
              <Fact
                label="Assessment"
                value={text(value.physician_assessment.summary)}
              />
              <Fact
                label="Uncertainty"
                value={text(value.physician_assessment.uncertainty)}
              />
            </>
          ) : (
            <Empty label="No effective physician assessment" />
          )}
          {value.physician_decision ? (
            <div className="vm-authority-block">
              <strong>Current non-revoked physician decision</strong>
              <p>
                {text(value.physician_decision.decision_type).replaceAll(
                  "_",
                  " ",
                )}
              </p>
              <p>{text(value.physician_decision.rationale)}</p>
              <Source value={value.physician_decision} idKey="decision_id" />
            </div>
          ) : (
            <Empty label="No current physician decision" />
          )}
          <small>
            Corrected, superseded and revoked records remain available in
            Clinical Reasoning history.
          </small>
        </Panel>

        <Panel
          title="Workflow state"
          link={`/cases/${caseId}/workflow`}
          linkLabel="Open Workflow"
        >
          {value.workflow ? (
            <>
              <Fact
                label="Current state"
                value={text(value.workflow.state).replaceAll("_", " ")}
              />
              <Fact
                label="Last transition"
                value={
                  value.workflow.last_transition_at
                    ? formatTimestamp(text(value.workflow.last_transition_at))
                    : "No transition recorded"
                }
              />
              <Source value={value.workflow} idKey="workflow_id" />
              <p className="vm-demo-notice">
                {text(value.workflow.demonstration_notice)}
              </p>
            </>
          ) : (
            <Empty label="No workflow instance" />
          )}
        </Panel>

        <Panel
          title="Active tasks and unresolved alerts"
          link={`/cases/${caseId}/workflow`}
          linkLabel="Manage in Workflow"
        >
          <div className="vm-case-ops-summary">
            <strong>{value.tasks.length}</strong>
            <span>active tasks</span>
            <strong>{value.alerts.length}</strong>
            <span>unresolved alerts</span>
          </div>
          {value.tasks.slice(0, 4).map((task) => (
            <div className="vm-compact-row" key={text(task.task_id)}>
              <span>{text(task.task_type).replaceAll("_", " ")}</span>
              <strong>{text(task.status)}</strong>
              <small>
                {task.due_at
                  ? `Due ${formatTimestamp(text(task.due_at))}`
                  : "No due time"}
              </small>
            </div>
          ))}
          {value.alerts.slice(0, 3).map((alert) => (
            <div
              className="vm-compact-row vm-compact-row--alert"
              key={text(alert.alert_id)}
            >
              <span>{text(alert.message)}</span>
              <strong>{text(alert.severity)}</strong>
            </div>
          ))}
          {!value.tasks.length && !value.alerts.length && (
            <Empty label="No active tasks or unresolved alerts" />
          )}
        </Panel>
      </div>

      <section
        className="vm-case-panel vm-case-timeline"
        aria-labelledby="recent-timeline-title"
      >
        <div className="vm-case-panel__heading">
          <h2 id="recent-timeline-title">Recent Timeline</h2>
          <Link href={`/cases/${caseId}/timeline`}>View full Timeline</Link>
        </div>
        {value.timeline.length ? (
          value.timeline.map((event) => (
            <article key={text(event.timeline_event_id)}>
              <Clock3 size={15} aria-hidden />
              <div>
                <strong>{text(event.title)}</strong>
                <small>
                  {formatTimestamp(text(event.occurred_at))} ·{" "}
                  {text(event.source)}
                </small>
              </div>
            </article>
          ))
        ) : (
          <Empty label="No Timeline activity recorded" />
        )}
        <p className="vm-case-workspace__audit-link">
          Need provenance?{" "}
          <Link href={`/cases/${caseId}/audit`}>
            Open the complete Audit trail
          </Link>
          .
        </p>
      </section>
      <footer className="vm-case-workspace__footer">
        Research-use prototype. This workspace presents backend-owned evidence
        and navigation; it does not create clinical authority.
      </footer>
    </main>
  );
}

function Panel({
  title,
  link,
  linkLabel,
  ownerLabel,
  children,
}: {
  title: string;
  link?: string;
  linkLabel?: string;
  ownerLabel?: string;
  children: ReactNode;
}) {
  return (
    <section
      className="vm-case-panel"
      aria-labelledby={`${title.replaceAll(" ", "-").toLowerCase()}-title`}
    >
      <div className="vm-case-panel__heading">
        <h2 id={`${title.replaceAll(" ", "-").toLowerCase()}-title`}>
          {title}
        </h2>
        {link && linkLabel ? (
          <Link href={link}>{linkLabel}</Link>
        ) : (
          <span>{ownerLabel}</span>
        )}
      </div>
      {children}
    </section>
  );
}
function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="vm-case-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
function Source({
  value,
  idKey,
}: {
  value: Record<string, unknown>;
  idKey: string;
}) {
  return (
    <small className="vm-source-ref">
      Source {text(value[idKey])} · v{number(value.record_version)}
    </small>
  );
}
function Empty({ label }: { label: string }) {
  return <p className="vm-inline-empty">{label}. Unknown is not negative.</p>;
}
