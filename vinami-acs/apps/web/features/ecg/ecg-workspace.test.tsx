import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ECGWorkspaceView } from "@web/entities/ecg/model";
import { ECGWorkspace } from "./ecg-workspace";

const populated: ECGWorkspaceView = {
  caseId: "30000000-0000-4000-8000-000000000001",
  studies: [
    {
      studyId: "40000000-0000-4000-8000-000000000001",
      studyReference: "DEMO-12L-001",
      sourceType: "canonical_waveform",
      acquisitionAt: "2026-07-14T08:00:00Z",
      qualityStatus: "acceptable",
      samplingRateHz: 100,
      durationSeconds: 10,
      amplitudeUnit: "uV",
      leadConfiguration: "12-lead",
      waveformAvailable: true,
      preprocessingVersion: "canonical-normalization-1.0.0",
    },
  ],
  currentStudy: null,
  quality: {
    status: "acceptable",
    reasonCodes: [],
    affectedLeads: [],
    assessedAt: "2026-07-14T08:00:01Z",
    engineVersion: "technical-quality-1.0.0",
    suppressScoreEmphasis: false,
  },
  analyses: [
    {
      analysisId: "50000000-0000-4000-8000-000000000001",
      studyId: "40000000-0000-4000-8000-000000000001",
      status: "completed",
      qualityStatus: "acceptable",
      modelName: "vinami-deterministic-ecg-fixture",
      modelVersion: "r3-demo-1",
      providerName: "deterministic-mock",
      synthetic: true,
      completedAt: "2026-07-14T08:00:02Z",
      findings: [
        {
          code: "MI",
          label: "MI-related ECG pattern",
          score: 0.78,
          threshold: 0.5,
          thresholdMet: true,
          rank: 1,
          status: "above_threshold",
        },
        {
          code: "NORM",
          label: "NORM",
          score: 0.21,
          threshold: 0.5,
          thresholdMet: false,
          rank: 2,
          status: "below_threshold",
        },
      ],
      warnings: ["Model-attention aid; not causal clinical evidence."],
      explanationStatus: "available",
      explanationArtifactId: "60000000-0000-4000-8000-000000000001",
      safetyNotice: "Model scores are not clinical probabilities.",
    },
  ],
  interpretations: [],
  ingestionJobs: [],
  comparisons: [],
  comparisonReviews: [],
  reminders: [],
  capabilities: {
    hospital_ingestion: true,
    dynamic_ecg: true,
    repeat_ecg: true,
  },
  connectors: [],
  dataFreshness: "2026-07-14T08:00:03Z",
  waveform: {
    studyReference: "DEMO-12L-001",
    samplingRateHz: 100,
    amplitudeUnit: "uV",
    leads: Array.from({ length: 12 }, (_, index) => ({
      name: `L${index + 1}`,
      samples: [0, 1, -1, 0],
    })),
  },
  safetyNotice: "Model scores are not clinical probabilities.",
  technicalWarnings: [],
};
populated.currentStudy = populated.studies[0] ?? null;

describe("ECGWorkspace", () => {
  afterEach(cleanup);

  it("separates waveform evidence from ranked independent model outputs", () => {
    render(<ECGWorkspace caseId={populated.caseId} initialValue={populated} />);
    expect(screen.getAllByRole("img", { name: /dạng sóng/ })).toHaveLength(12);
    expect(screen.getByText("Mẫu ECG liên quan MI")).toBeInTheDocument();
    expect(
      screen.getByText(/điểm số không cần cộng lại bằng 1/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/không thể loại trừ nhồi máu cơ tim cấp/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/không phải xác suất lâm sàng/i),
    ).toBeInTheDocument();
  });

  it("renders a safe empty state with an explicit synthetic-data action", () => {
    render(
      <ECGWorkspace
        caseId={populated.caseId}
        initialValue={{
          ...populated,
          studies: [],
          currentStudy: null,
          quality: null,
          analyses: [],
          waveform: null,
        }}
      />,
    );
    expect(screen.getByText("Ca này chưa có ECG")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Nạp ECG 12 chuyển đạo mô phỏng" }),
    ).toBeInTheDocument();
  });
});
