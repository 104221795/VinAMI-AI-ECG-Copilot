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
      source: "workflow_operations",
      severity: "urgent",
      status: "active",
      raised_at: "2026-07-15T14:31:00Z",
      escalation_level: 1,
      message: "A time-bound clinical task is overdue.",
    },
  ],
  automation: {
    policy_version: "vinami-r13-r14-r21-demo-v1",
    safety_notice: "Demonstration automation - not for clinical use.",
    completeness: {
      score: 67,
      status: "incomplete",
      required_count: 6,
      current_count: 4,
      items: [],
      missing_evidence: ["ecg"],
      stale_evidence: [],
      technical_limits: [],
      not_negative_evidence_notice:
        "Missing, unknown, stale, or technically limited evidence is not negative evidence.",
    },
    suggested_tasks: [
      {
        suggestion_id: "suggest-repeat-ecg",
        task_type: "repeat_ecg",
        priority: "urgent",
        due_state: "due_now",
        due_at: "2026-07-15T15:00:00Z",
        reason: "No current ECG evidence is available.",
        evidence_gaps: ["ecg"],
      },
    ],
    alert_digest: [
      {
        group_key: "task-overdue",
        alert_type: "task_overdue",
        source: "workflow_operations",
        severity: "urgent",
        status: "active",
        count: 1,
        representative_alert_id: "17ebaf15-5cc7-47bc-b6d3-ef68ea5dc84a",
        alert_ids: ["17ebaf15-5cc7-47bc-b6d3-ef68ea5dc84a"],
        latest_raised_at: "2026-07-15T14:31:00Z",
        max_escalation_level: 1,
        message: "A time-bound clinical task is overdue.",
      },
    ],
  },
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
    expect(screen.getByText("1 quá hạn")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("row", { name: /SYN-R7-001/i }), {
      key: "Enter",
    });
    expect(onSelect).toHaveBeenCalledWith(row.case_id);
  });

  it("does not render placeholder due dates as real clinical dates", () => {
    render(
      <ActiveCaseTable
        rows={[{ ...row, next_due_at: "2020-01-01T00:00:00Z" }]}
        referenceTime="2026-07-15T15:00:00Z"
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Chưa đặt hạn xử lý")).toBeInTheDocument();
    expect(screen.queryByText(/1 Jan 2020/)).not.toBeInTheDocument();
  });

  it("shows decision, evidence, tasks, alerts and workspace links", () => {
    render(
      <SelectedCasePanel
        row={row}
        referenceTime="2026-07-15T15:00:00Z"
        onClear={vi.fn()}
      />,
    );
    expect(screen.getByText("Quyết định của bác sĩ")).toBeInTheDocument();
    expect(
      screen.getByText(/Physician requested technical/),
    ).toBeInTheDocument();
    expect(screen.getByText("Gợi ý công việc từ backend")).toBeInTheDocument();
    expect(screen.getAllByText("ECG").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Quy trình" })).toHaveAttribute(
      "href",
      `/cases/${row.case_id}/workflow`,
    );
    expect(screen.getByText(/AI không quyết định ưu tiên/)).toBeInTheDocument();
  });
});
