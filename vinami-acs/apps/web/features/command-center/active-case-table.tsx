"use client";

import { PriorityBadge, StatusBadge } from "@vinami/ui";
import {
  formatRelative,
  formatTimestamp,
  shortReference,
} from "@web/shared/formatting";
import type { CommandCenterCaseView } from "./model";

export function ActiveCaseTable({
  rows,
  selectedCaseId,
  onSelect,
  referenceTime,
}: {
  rows: CommandCenterCaseView[];
  selectedCaseId?: string;
  onSelect: (caseId: string) => void;
  referenceTime: string;
}) {
  const now = new Date(referenceTime).getTime();
  return (
    <div className="vm-table-wrap vm-command-table-wrap">
      <table
        className="vm-table vm-command-table"
        aria-label="Active ACS operational case queue"
      >
        <thead>
          <tr>
            <th scope="col">Priority</th>
            <th scope="col">Patient / case</th>
            <th scope="col">Workflow</th>
            <th scope="col">Evidence</th>
            <th scope="col">Tasks</th>
            <th scope="col">Alerts</th>
            <th scope="col">Next due</th>
            <th scope="col">Owner</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.case_id}
              tabIndex={0}
              aria-selected={row.case_id === selectedCaseId}
              onClick={() => onSelect(row.case_id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(row.case_id);
                }
              }}
            >
              <td>
                <PriorityBadge priority={row.operational_priority} />
                <small className="vm-cell-note">{row.priority_reason}</small>
              </td>
              <td>
                <span className="vm-cell-primary">
                  {row.patient_reference}
                  <small>
                    {shortReference(row.case_id, "CASE")} · {row.location}
                  </small>
                </span>
              </td>
              <td>
                <StatusBadge status={row.workflow_state ?? row.case_status} />
              </td>
              <td>
                <StatusBadge status={row.evidence_status} />
                {row.missing_evidence.length > 0 && (
                  <small className="vm-cell-note">
                    {row.missing_evidence.length} missing
                  </small>
                )}
              </td>
              <td>
                <strong className="vm-tabular">{row.active_task_count}</strong>
                {row.overdue_task_count > 0 && (
                  <small className="vm-cell-note vm-text-urgent">
                    {row.overdue_task_count} overdue
                  </small>
                )}
              </td>
              <td>
                <strong className="vm-tabular">
                  {row.unresolved_alert_count}
                </strong>
              </td>
              <td
                title={
                  row.next_due_at ? formatTimestamp(row.next_due_at) : undefined
                }
              >
                {row.next_due_at
                  ? formatRelative(row.next_due_at, now)
                  : "Not scheduled"}
              </td>
              <td>{ownerLabel(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ownerLabel(row: CommandCenterCaseView) {
  if (row.owner_user_id) return shortReference(row.owner_user_id, "USR");
  if (row.owner_team_id) return shortReference(row.owner_team_id, "TEAM");
  return "Unassigned";
}
