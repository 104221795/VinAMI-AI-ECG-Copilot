"use client";

import type { CommandCenterQuery } from "@vinami/api-client";

export interface CommandFilters {
  priority: "" | "routine" | "urgent" | "critical";
  workflowState: "" | NonNullable<CommandCenterQuery["workflow_state"]>;
  overdue: "" | "true" | "false";
  alertStatus: "" | "active" | "acknowledged" | "unresolved" | "none";
  evidenceStatus: "" | "current" | "missing" | "stale" | "technical_limit";
  owner: string;
  sort: "priority" | "opened_at" | "next_due_at" | "latest_activity";
  direction: "asc" | "desc";
}

const workflowStates = [
  "NEW",
  "TRIAGE_IN_PROGRESS",
  "AWAITING_ECG",
  "ECG_UNDER_REVIEW",
  "AWAITING_TROPONIN",
  "OBSERVATION",
  "PHYSICIAN_REVIEW_REQUIRED",
  "PATHWAY_SELECTED",
  "TRANSFER_IN_PROGRESS",
  "CATH_LAB_REVIEW",
  "DISCHARGE_REVIEW",
];

export function FilterBar({
  value,
  onChange,
}: {
  value: CommandFilters;
  onChange: (next: CommandFilters) => void;
}) {
  const set = <Key extends keyof CommandFilters>(
    field: Key,
    fieldValue: CommandFilters[Key],
  ) => onChange({ ...value, [field]: fieldValue });
  return (
    <section className="vm-command-filters" aria-label="Command Center filters">
      <label className="vm-field">
        <span>Operational priority</span>
        <select
          value={value.priority}
          onChange={(event) =>
            set("priority", event.target.value as CommandFilters["priority"])
          }
        >
          <option value="">All priorities</option>
          <option value="critical">Critical</option>
          <option value="urgent">Urgent</option>
          <option value="routine">Routine</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Workflow state</span>
        <select
          value={value.workflowState}
          onChange={(event) =>
            set(
              "workflowState",
              event.target.value as CommandFilters["workflowState"],
            )
          }
        >
          <option value="">All workflow states</option>
          {workflowStates.map((state) => (
            <option key={state} value={state}>
              {formatCode(state)}
            </option>
          ))}
        </select>
      </label>
      <label className="vm-field">
        <span>Due state</span>
        <select
          value={value.overdue}
          onChange={(event) =>
            set("overdue", event.target.value as CommandFilters["overdue"])
          }
        >
          <option value="">All due states</option>
          <option value="true">Overdue</option>
          <option value="false">Not overdue</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Alerts</span>
        <select
          value={value.alertStatus}
          onChange={(event) =>
            set(
              "alertStatus",
              event.target.value as CommandFilters["alertStatus"],
            )
          }
        >
          <option value="">All alert states</option>
          <option value="unresolved">Any unresolved</option>
          <option value="active">Active</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="none">No unresolved alert</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Evidence</span>
        <select
          value={value.evidenceStatus}
          onChange={(event) =>
            set(
              "evidenceStatus",
              event.target.value as CommandFilters["evidenceStatus"],
            )
          }
        >
          <option value="">All evidence states</option>
          <option value="current">Current</option>
          <option value="missing">Missing</option>
          <option value="stale">Stale</option>
          <option value="technical_limit">Technical limit</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Owner or team ID</span>
        <input
          value={value.owner}
          placeholder="UUID"
          onChange={(event) => set("owner", event.target.value)}
        />
      </label>
      <label className="vm-field">
        <span>Sort by</span>
        <select
          value={value.sort}
          onChange={(event) =>
            set("sort", event.target.value as CommandFilters["sort"])
          }
        >
          <option value="priority">Operational priority</option>
          <option value="next_due_at">Next due time</option>
          <option value="latest_activity">Latest activity</option>
          <option value="opened_at">Case opened</option>
        </select>
      </label>
      <label className="vm-field">
        <span>Direction</span>
        <select
          value={value.direction}
          onChange={(event) =>
            set("direction", event.target.value as CommandFilters["direction"])
          }
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
      </label>
    </section>
  );
}

function formatCode(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}
