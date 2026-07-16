import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CommandCenterCaseView } from "./model";
import { ActiveCaseTable } from "./active-case-table";
import { SelectedCasePanel } from "./selected-case-panel";

const row: CommandCenterCaseView = {
  case_id: "cbbc0872-798f-40c5-83e3-64d66176e73b",
  encounter_id: "2a46ec31-5371-4424-99f0-c3aee1399e69",
  patient_id: "8b78f75f-dfce-4ed4-948a-b25e186b645a",
  patient_reference: "SYN-R7-001",
  age_band: "45-64",
  sex_at_birth: "female",
  location: "Emergency Department",
  case_status: "open",
  case_priority: "urgent",
  case_version: 2,
  opened_at: "2026-07-15T14:00:00Z",
  workflow_id: "ac2d5e2c-2ea2-4b60-8070-a33c91fbc359",
  workflow_state: "PHYSICIAN_REVIEW_REQUIRED",
  workflow_version: 3,
  operational_priority: "critical",
  priority_reason: "Persisted overdue clinical task",
  active_task_count: 1,
  overdue_task_count: 1,
  unresolved_alert_count: 1,
  next_due_at: "2026-07-15T14:30:00Z",
  oldest_overdue_at: "2026-07-15T14:31:00Z",
  owner_user_id: null,
  owner_team_id: null,
  snapshot_id: "fe7b4197-59df-457e-88b7-60fe8b1a512a",
  snapshot_created_at: "2026-07-15T14:15:00Z",
  evidence_status: "missing",
  evidence_freshness: { triage: "current", ecg: "missing" },
  missing_evidence: ["ecg"],
  technical_limits: [],
  decision_id: "a8ecb993-750d-4491-8da4-e2c1669b1c43",
  decision_type: "request_repeat_ecg",
  decision_rationale: "Physician requested technical reassessment.",
  decision_recorded_at: "2026-07-15T14:20:00Z",
  latest_activity_at: "2026-07-15T14:31:00Z",
  update_token: "2:3:2:1",
  tasks: [
    {
      task_id: "43400372-36f7-4b1d-8f45-807230caaf62",
      task_type: "repeat_ecg",
      status: "overdue",
      priority: "urgent",
      due_at: "2026-07-15T14:30:00Z",
      overdue_at: "2026-07-15T14:31:00Z",
      escalation_level: 1,
      owner_user_id: null,
      owner_team_id: null,
    },
  ],
  alerts: [
    {
      alert_id: "17ebaf15-5cc7-47bc-b6d3-ef68ea5dc84a",
      alert_type: "task_overdue",
      severity: "urgent",
      status: "active",
      raised_at: "2026-07-15T14:31:00Z",
      escalation_level: 1,
    },
  ],
};

describe("R7 Command Center presentation", () => {
  it("renders authoritative queue state and supports keyboard selection", () => {
    const onSelect = vi.fn();
    render(
      <ActiveCaseTable
        rows={[row]}
        referenceTime="2026-07-15T15:00:00Z"
        onSelect={onSelect}
      />,
    );
    expect(screen.getByText("SYN-R7-001")).toBeInTheDocument();
    expect(screen.getByText("1 overdue")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("row", { name: /SYN-R7-001/i }), {
      key: "Enter",
    });
    expect(onSelect).toHaveBeenCalledWith(row.case_id);
  });

  it("shows decision, evidence, tasks, alerts and workspace links", () => {
    render(
      <SelectedCasePanel
        row={row}
        referenceTime="2026-07-15T15:00:00Z"
        onClear={vi.fn()}
      />,
    );
    expect(screen.getByText("Physician decision")).toBeInTheDocument();
    expect(
      screen.getByText(/Physician requested technical/),
    ).toBeInTheDocument();
    expect(screen.getByText("Missing or unknown:")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Workflow" })).toHaveAttribute(
      "href",
      `/cases/${row.case_id}/workflow`,
    );
    expect(
      screen.getByText(/AI output does not determine priority/),
    ).toBeInTheDocument();
  });
});
