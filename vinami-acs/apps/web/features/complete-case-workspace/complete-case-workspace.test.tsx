import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { CompleteCaseWorkspace } from "./complete-case-workspace";
import type { CompleteCaseWorkspaceView } from "./model";

const caseId = "30000000-0000-4000-8000-000000000008";
const fixture: CompleteCaseWorkspaceView = {
  case_id: caseId,
  encounter_id: "30000000-0000-4000-8000-000000000009",
  patient_id: "30000000-0000-4000-8000-000000000010",
  patient_reference: "SYN-R8-001",
  patient_name: "Nguyen An",
  age_band: "45-64",
  sex_at_birth: "female",
  location: "Emergency Department",
  encounter_status: "active",
  case_status: "open",
  case_priority: "urgent",
  opening_reason: "Suspected ACS review",
  opened_at: "2026-07-16T08:00:00Z",
  last_updated_at: "2026-07-16T08:20:00Z",
  case_version: 3,
  triage: {
    assessment_id: "31000000-0000-4000-8000-000000000001",
    record_version: 1,
    chief_complaint: "Chest discomfort",
    symptom_description: "Central pressure",
    occurred_at: "2026-07-16T08:02:00Z",
  },
  vitals: {
    vital_set_id: "32000000-0000-4000-8000-000000000001",
    record_version: 1,
    measurements: [{ kind: "heart_rate", value: 82, unit: "beats/min" }],
  },
  ecg: {
    study_id: "33000000-0000-4000-8000-000000000001",
    record_version: 2,
    study_reference: "ECG-R8-01",
    quality_status: "acceptable",
    acquisition_at: "2026-07-16T08:05:00Z",
    analysis: {
      status: "completed",
      model_name: "ConvNeXtV2 research adapter",
      model_version: "1.0",
    },
    physician_interpretation: {
      structured_interpretation:
        "Physician review requires clinical correlation.",
    },
  },
  troponin: {
    result_count: 2,
    latest_result: {
      result_id: "34000000-0000-4000-8000-000000000001",
      record_version: 1,
      value: "12.40",
      unit: "ng/L",
      assay_name: "Demonstration assay",
      specimen_collected_at: "2026-07-16T08:15:00Z",
    },
    latest_delta: {
      absolute_change: "2.40",
      unit: "ng/L",
      compatibility_status: "compatible",
    },
  },
  evidence_snapshot: { snapshot_id: "snapshot", record_version: 1 },
  physician_assessment: {
    summary: "Integrated physician assessment",
    uncertainty: "Serial review remains required",
  },
  physician_decision: {
    decision_id: "35000000-0000-4000-8000-000000000001",
    record_version: 1,
    decision_type: "request_repeat_troponin",
    rationale: "Physician requested another sample.",
  },
  workflow: {
    workflow_id: "36000000-0000-4000-8000-000000000001",
    version: 2,
    state: "PHYSICIAN_REVIEW_REQUIRED",
    last_transition_at: "2026-07-16T08:20:00Z",
    demonstration_notice: "Demonstration workflow - not for clinical use.",
  },
  tasks: [
    {
      task_id: "37000000-0000-4000-8000-000000000001",
      task_type: "repeat_troponin",
      status: "assigned",
      due_at: "2026-07-16T08:40:00Z",
    },
  ],
  alerts: [
    {
      alert_id: "38000000-0000-4000-8000-000000000001",
      message: "Physician review required",
      severity: "urgent",
    },
  ],
  timeline: [
    {
      timeline_event_id: "39000000-0000-4000-8000-000000000001",
      title: "Physician decision recorded",
      occurred_at: "2026-07-16T08:20:00Z",
      source: "clinical-reasoning",
    },
  ],
  evidence_status: "missing",
  missing_evidence: ["repeat_troponin"],
  stale_evidence: [],
  technical_limits: [],
  update_token: "r8-token-1",
  evaluated_at: new Date().toISOString(),
};

vi.mock("@web/shared/api/browser", () => ({
  createBrowserApiClient: () => ({ getCompleteCaseWorkspace: vi.fn() }),
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

describe("R8 CompleteCaseWorkspace", () => {
  it("presents effective evidence, physician authority and owning-workspace links", () => {
    render(
      <Wrapper>
        <CompleteCaseWorkspace caseId={caseId} initialValue={fixture} />
      </Wrapper>,
    );
    expect(
      screen.getByRole("heading", { name: "Nguyen An" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Chest discomfort")).toBeInTheDocument();
    expect(
      screen.getByText("Current non-revoked physician decision"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Physician requested another sample."),
    ).toBeInTheDocument();
    expect(screen.getByText("Physician review required")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open ECG workspace" }),
    ).toHaveAttribute("href", `/cases/${caseId}/ecg`);
    expect(screen.getByRole("link", { name: "Audit" })).toHaveAttribute(
      "href",
      `/cases/${caseId}/audit`,
    );
    expect(
      screen.getByText(/not a diagnosis or clinical probability/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Missing or unknown evidence is not negative evidence."),
    ).toBeInTheDocument();
  });
});
