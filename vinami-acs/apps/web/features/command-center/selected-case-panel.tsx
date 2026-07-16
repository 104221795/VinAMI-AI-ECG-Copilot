"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  Button,
  ClinicalCard,
  EmptyState,
  PriorityBadge,
  StatusBadge,
} from "@vinami/ui";
import {
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";
import type { CommandCenterCaseView } from "./model";

export function SelectedCasePanel({
  row,
  onClear,
  referenceTime,
}: {
  row?: CommandCenterCaseView;
  onClear: () => void;
  referenceTime: string;
}) {
  if (!row) {
    return (
      <ClinicalCard className="vm-selected-panel">
        <EmptyState
          title="No case selected"
          description="Select a queue row to review persisted operational context."
        />
      </ClinicalCard>
    );
  }
  const now = new Date(referenceTime).getTime();
  return (
    <aside
      className="vm-command-quick-view"
      aria-label="Selected case quick view"
    >
      <ClinicalCard
        title="Selected case"
        className="vm-selected-panel"
        action={<Button onClick={onClear}>Clear</Button>}
      >
        <div className="vm-case-header">
          <PriorityBadge priority={row.operational_priority} />
          <StatusBadge status={row.workflow_state ?? row.case_status} />
        </div>
        <p className="vm-priority-reason">{row.priority_reason}</p>
        <dl className="vm-definition-list">
          <dt>Patient</dt>
          <dd>{row.patient_reference}</dd>
          <dt>Case</dt>
          <dd>{shortReference(row.case_id, "CASE")}</dd>
          <dt>Location</dt>
          <dd>{row.location}</dd>
          <dt>Elapsed</dt>
          <dd title={formatTimestamp(row.opened_at)}>
            {formatRelative(row.opened_at, now)}
          </dd>
          <dt>Latest activity</dt>
          <dd title={formatTimestamp(row.latest_activity_at)}>
            {formatRelative(row.latest_activity_at, now)}
          </dd>
          <dt>Owner</dt>
          <dd>{ownerLabel(row)}</dd>
        </dl>

        <section className="vm-quick-section">
          <h3>Physician decision</h3>
          {row.decision_id ? (
            <>
              <strong>
                {formatCode(row.decision_type ?? "documented decision")}
              </strong>
              <p>{row.decision_rationale}</p>
              <small>
                Effective persisted record ·{" "}
                {shortReference(row.decision_id, "DEC")}
              </small>
            </>
          ) : (
            <p>No effective physician decision is currently persisted.</p>
          )}
        </section>

        <section className="vm-quick-section">
          <h3>Evidence status</h3>
          <StatusBadge status={row.evidence_status} />
          <div className="vm-evidence-status-grid">
            {Object.entries(row.evidence_freshness).map(([source, status]) => (
              <span key={source}>
                <strong>{formatCode(source)}</strong>
                <StatusBadge status={status} />
              </span>
            ))}
          </div>
          {row.missing_evidence.length > 0 && (
            <p>
              <strong>Missing or unknown:</strong>{" "}
              {row.missing_evidence.map(formatCode).join(", ")}
            </p>
          )}
          {row.technical_limits.length > 0 && (
            <p>
              <strong>Technical limits:</strong>{" "}
              {row.technical_limits.join("; ")}
            </p>
          )}
        </section>

        <section className="vm-quick-section">
          <h3>Active tasks</h3>
          {row.tasks.length === 0 ? (
            <p>No active operational task.</p>
          ) : (
            <ul className="vm-compact-list">
              {row.tasks.slice(0, 4).map((task) => (
                <li key={task.task_id}>
                  <span>
                    <strong>{formatCode(task.task_type)}</strong>
                    <small>{formatCode(task.status)}</small>
                  </span>
                  <span>
                    {task.due_at
                      ? formatRelative(task.due_at, now)
                      : "No due time"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="vm-quick-section">
          <h3>Unresolved alerts</h3>
          {row.alerts.length === 0 ? (
            <p>No unresolved operational alert.</p>
          ) : (
            <ul className="vm-compact-list">
              {row.alerts.slice(0, 4).map((alert) => (
                <li key={alert.alert_id}>
                  <span>
                    <strong>{formatCode(alert.alert_type)}</strong>
                    <small>{formatCode(alert.status)}</small>
                  </span>
                  <StatusBadge status={alert.severity} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <nav
          className="vm-workspace-links"
          aria-label="Selected case workspaces"
        >
          <WorkspaceLink href={`/cases/${row.case_id}/documentation`}>
            Triage / Vitals
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/clinical-reasoning`}>
            Clinical Reasoning
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/ecg`}>ECG</WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/troponin`}>
            Troponin
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/workflow`}>
            Workflow
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/timeline`}>
            Timeline
          </WorkspaceLink>
          <WorkspaceLink href={`/cases/${row.case_id}/audit`}>
            Audit
          </WorkspaceLink>
        </nav>
        <p className="vm-safety-note">
          Operational overview only. AI output does not determine priority or
          clinical authority.
        </p>
      </ClinicalCard>
    </aside>
  );
}

function ownerLabel(row: CommandCenterCaseView) {
  if (row.owner_user_id) return shortReference(row.owner_user_id, "USR");
  if (row.owner_team_id) return shortReference(row.owner_team_id, "TEAM");
  return "Unassigned";
}

function formatCode(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function WorkspaceLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      onMouseDown={(event) => {
        if (
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.altKey ||
          event.shiftKey
        ) {
          return;
        }
        event.preventDefault();
        window.location.assign(href);
      }}
    >
      {children}
    </Link>
  );
}
