import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ClinicalDocumentationView } from "@web/entities/clinical-documentation/model";
import { ClinicalDocumentationWorkspace } from "./clinical-documentation-workspace";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const current: ClinicalDocumentationView = {
  currentTriage: {
    assessmentId: "10000000-0000-4000-8000-000000000001",
    revisionNumber: 2,
    status: "correction",
    source: "structured-form",
    recordedBy: "nurse",
    occurredAt: "2026-07-14T08:00:00Z",
    recordedAt: "2026-07-14T08:01:00Z",
    recordVersion: 2,
    chiefComplaint: "Synthetic documented symptom",
    symptomOnsetState: "unknown",
    symptomOnsetAt: null,
    symptomOnsetPrecision: null,
    symptomDescription: "Patient-reported wording",
    associatedSymptoms: [
      { name: "dyspnoea", state: "absent", note: null },
      { name: "nausea", state: "not_assessed", note: null },
    ],
    riskFactors: [{ name: "smoking history", state: "unknown", note: null }],
    correctsAssessmentId: "10000000-0000-4000-8000-000000000000",
    correctionReason: "Patient clarified wording",
  },
  triageHistory: [],
  latestVitals: {
    vitalSetId: "20000000-0000-4000-8000-000000000001",
    sequenceNumber: 1,
    revisionNumber: 1,
    source: "bedside-entry",
    recordedBy: "nurse",
    observedAt: "2026-07-14T08:02:00Z",
    recordedAt: "2026-07-14T08:03:00Z",
    recordVersion: 1,
    measurements: [
      {
        kind: "heart_rate",
        value: 72,
        unit: "beats/min",
        source: "manual-entry",
        observedAt: "2026-07-14T08:02:00Z",
        qualityStatus: "accepted",
      },
    ],
    supplementalOxygenState: "not_assessed",
    correctsVitalSetId: null,
    correctionReason: null,
  },
  vitalHistory: [],
  missingDocumentation: [],
  completenessPolicyVersion: "r2-documentation-v1",
  dataFreshnessAt: "2026-07-14T08:04:00Z",
  caseVersion: 1,
};

describe("ClinicalDocumentationWorkspace", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(cleanup);

  it("renders explicit documentation states without clinical inference", () => {
    render(
      <ClinicalDocumentationWorkspace
        caseId="30000000-0000-4000-8000-000000000001"
        value={current}
      />,
    );
    expect(
      screen.getByText("Documentation policy complete"),
    ).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getByText("not assessed")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
    expect(screen.getByText("beats/min")).toBeInTheDocument();
    expect(screen.getByText(/No diagnosis, pathway/)).toBeInTheDocument();
  });

  it("opens append-only correction forms with required reason fields", () => {
    render(
      <ClinicalDocumentationWorkspace
        caseId="30000000-0000-4000-8000-000000000001"
        value={current}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Correct entry" }));
    expect(screen.getByText("Correction reason")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review correction" }),
    ).toBeInTheDocument();
  });

  it("shows neutral empty and backend completeness states", () => {
    render(
      <ClinicalDocumentationWorkspace
        caseId="30000000-0000-4000-8000-000000000001"
        value={{
          ...current,
          currentTriage: null,
          latestVitals: null,
          missingDocumentation: [
            {
              identifier: "chief_complaint",
              description: "Chief complaint not documented",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("1 documentation gap")).toBeInTheDocument();
    expect(
      screen.getByText("No triage assessment recorded"),
    ).toBeInTheDocument();
    expect(screen.getByText("No vital observation set")).toBeInTheDocument();
  });
});
