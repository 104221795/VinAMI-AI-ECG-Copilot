import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TroponinWorkspaceView } from "@web/entities/troponin/model";
import { TroponinWorkspace } from "./troponin-workspace";

const result = {
  result_id: "40000000-0000-4000-8000-000000000001",
  assay_id: "40000000-0000-4000-8000-000000000002",
  assay_code: "DEMO-HS-CTNI-01",
  assay_display_name: "Demonstration hs-cTnI",
  assay_category: "hs_ctni",
  manufacturer: "Synthetic catalog",
  platform: "Mock platform",
  assay_version: "demo-1",
  analyte: "cardiac_troponin_i",
  original_value: "12.4",
  original_unit: "ng/L",
  normalized_value: "12.4",
  normalized_unit: "ng/L",
  conversion_status: "identity",
  conversion_version: "v1",
  specimen_type: "plasma",
  specimen_collected_at: "2026-07-14T10:00:00Z",
  resulted_at: "2026-07-14T10:01:00Z",
  result_status: "final",
  reference_limit_value: null,
  reference_limit_unit: null,
  reference_limit_source: null,
  quality_flags: [],
  source_system: "test",
  source_type: "manual",
  source_result_id: "result-source",
  source_identity: "result-source",
  source_revision: 1,
  accession_number: null,
  supersedes_result_id: null,
  amendment_reason: null,
  recorded_by_role: "physician",
  recorded_at: "2026-07-14T10:01:00Z",
  correlation_id: "50000000-0000-4000-8000-000000000001",
  record_version: 1,
};

const fixture: TroponinWorkspaceView = {
  clinical_case_id: "30000000-0000-4000-8000-000000000001",
  case_version: 1,
  effective_results: [result],
  result_history: [result],
  latest_result: result,
  deltas: [],
  import_jobs: [],
  clinician_reviews: [
    {
      review_id: "60000000-0000-4000-8000-000000000001",
      clinical_case_id: "30000000-0000-4000-8000-000000000001",
      referenced_result_ids: [result.result_id],
      actor_id: "70000000-0000-4000-8000-000000000001",
      actor_role: "physician",
      review_status: "evidence_reviewed",
      incompatibility_acknowledged: false,
      quality_limitation_acknowledged: false,
      repeat_measurement_requested: true,
      repeat_measurement_reason: "Repeat synthetic specimen.",
      note: "Original review.",
      occurred_at: "2026-07-14T10:01:00Z",
      recorded_at: "2026-07-14T10:01:00Z",
      correlation_id: "50000000-0000-4000-8000-000000000001",
      supersedes_review_id: null,
      correction_reason: null,
      record_version: 1,
    },
  ],
  latest_clinician_review: null,
  repeat_measurement_requests: [
    {
      request_id: "80000000-0000-4000-8000-000000000001",
      clinical_case_id: "30000000-0000-4000-8000-000000000001",
      source_result_id: result.result_id,
      requested_by_actor_id: "70000000-0000-4000-8000-000000000001",
      reason: "Repeat synthetic specimen.",
      requested_at: "2026-07-14T10:01:00Z",
      status: "requested",
      acknowledged_by_actor_id: null,
      acknowledged_at: null,
      completed_result_id: null,
      completed_at: null,
      cancellation_reason: null,
      correlation_id: "50000000-0000-4000-8000-000000000001",
      record_version: 1,
    },
  ],
  data_freshness: "2026-07-14T10:01:00Z",
  capabilities: {
    manual_entry: true,
    mock_laboratory_import: true,
    live_lis: false,
    amendment: true,
    clinician_review: true,
    repeat_measurement: true,
  },
  safety_notice: "Clinician interpretation required.",
};

afterEach(() => cleanup());

describe("TroponinWorkspace R4.1", () => {
  it("renders repeat lifecycle details and sends an idempotent acknowledge command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ ...fixture, repeat_measurement_requests: [] }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", vi.fn().mockReturnValue(true));
    render(
      <TroponinWorkspace
        caseId={fixture.clinical_case_id}
        initialValue={fixture}
      />,
    );

    expect(screen.getByText("Request lifecycle")).toBeVisible();
    expect(screen.getByText("Repeat synthetic specimen.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Acknowledge" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain(
      "/repeat-troponin-requests/80000000-0000-4000-8000-000000000001/acknowledge",
    );
    expect(options.headers).toMatchObject({
      "Idempotency-Key": expect.any(String),
    });
  });

  it("shows the immutable review correction form and requires a reason", () => {
    render(
      <TroponinWorkspace
        caseId={fixture.clinical_case_id}
        initialValue={{
          ...fixture,
          latest_clinician_review: fixture.clinician_reviews[0] ?? null,
        }}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Correct current review" }),
    );
    fireEvent.submit(
      screen
        .getByRole("button", { name: "Confirm correction" })
        .closest("form")!,
    );
    expect(
      screen.getByText(/correction_reason: A correction reason is required/i),
    ).toBeVisible();
  });
});
