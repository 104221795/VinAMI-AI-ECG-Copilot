import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { DecisionView } from "@web/features/clinical-reasoning/model";
import type { WorkflowOperationsView } from "./model";
import { WorkflowOperationsWorkspace } from "./workflow-operations-workspace";

const caseId = "30000000-0000-4000-8000-000000000001";
const actorId = "60000000-0000-4000-8000-000000000001";
const fixture: WorkflowOperationsView = {
  case_id: caseId,
  case_version: 1,
  workflow: {
    workflow_id: "70000000-0000-4000-8000-000000000001",
    state: "physician_review_required",
    version: 2,
    definition_version: "1.0.0",
    demonstration_notice: "Demonstration workflow - not for clinical use.",
  },
  tasks: [
    {
      task_id: "80000000-0000-4000-8000-000000000001",
      case_id: caseId,
      workflow_id: "70000000-0000-4000-8000-000000000001",
      task_type: "repeat_ecg",
      status: "assigned",
      priority: "urgent",
      version: 2,
      created_at: "2026-07-15T08:00:00Z",
      created_by: actorId,
      due_at: "2026-07-15T08:15:00Z",
      originating_decision_id: "90000000-0000-4000-8000-000000000001",
      source_type: "physician_decision",
      source_id: "90000000-0000-4000-8000-000000000001",
      owner_user_id: actorId,
      owner_team_id: null,
      acknowledged_at: null,
      started_at: null,
      completed_at: null,
      outcome: null,
      cancelled_at: null,
      cancellation_reason: null,
      overdue_at: null,
      escalation_level: 0,
      history: [],
      originating_decision: {
        decision_id: "90000000-0000-4000-8000-000000000001",
        decision_type: "request_repeat_ecg",
        status: "active",
        recorded_at: "2026-07-15T07:59:00Z",
        rationale: "Repeat ECG requested by physician.",
      },
    },
  ],
  alerts: [
    {
      alert_id: "a0000000-0000-4000-8000-000000000001",
      case_id: caseId,
      workflow_id: "70000000-0000-4000-8000-000000000001",
      task_id: "80000000-0000-4000-8000-000000000001",
      alert_type: "task_overdue",
      source: "workflow_operations",
      severity: "urgent",
      message: "Human review required.",
      status: "active",
      version: 1,
      raised_at: "2026-07-15T08:16:00Z",
      acknowledged_at: null,
      resolved_at: null,
      resolution_reason: null,
      escalation_level: 0,
      history: [],
    },
  ],
  safety_notice: "Task completion does not imply diagnosis or case closure.",
};

const decisions: DecisionView[] = [
  {
    decision_id: "b0000000-0000-4000-8000-000000000001",
    snapshot_id: "c0000000-0000-4000-8000-000000000001",
    assessment_id: "d0000000-0000-4000-8000-000000000001",
    decision_type: "request_cath_lab_review",
    status: "active",
    revision_number: 1,
    record_version: 1,
    rationale: "Physician specialist review request.",
    uncertainty: "Review remains required.",
    evidence_references: ["clinical_case:v1"],
    recorded_at: "2026-07-15T08:02:00Z",
    corrects_decision_id: null,
    correction_reason: null,
    workflow_authorization_id: "e0000000-0000-4000-8000-000000000001",
    effective: true,
  },
];

vi.mock("@web/shared/api/browser", () => ({
  createBrowserApiClient: () => ({
    getWorkflowOperationsWorkspace: vi.fn().mockResolvedValue(fixture),
    generateWorkflowTask: vi.fn(),
    changeWorkflowTask: vi.fn(),
    changeWorkflowAlert: vi.fn(),
    evaluateWorkflowOverdue: vi.fn(),
  }),
}));

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      {children}
    </QueryClientProvider>
  );
}

describe("WorkflowOperationsWorkspace", () => {
  it("shows authoritative tasks and opens task, alert, and generation dialogs", () => {
    render(
      <Wrapper>
        <WorkflowOperationsWorkspace
          caseId={caseId}
          actorId={actorId}
          initialValue={fixture}
          decisions={decisions}
        />
      </Wrapper>,
    );
    expect(
      screen.getByRole("heading", { name: "Repeat ECG" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Evidence and physician-directed operations",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Follow-up scheduling")).toBeInTheDocument();
    expect(
      screen.getByText(/hospital calendar integration/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Physician request for cath-lab review"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Acknowledge" })[0]!);
    expect(
      screen.getByRole("dialog", { name: "Acknowledge task" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    fireEvent.click(
      screen.getByRole("button", { name: "Create operational task" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Create operational task" }),
    ).toBeInTheDocument();
  });
});
