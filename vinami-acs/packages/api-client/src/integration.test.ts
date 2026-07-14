import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { VinamiApiClient, VinamiApiError } from "./index";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("generated API adapter", () => {
  it("sends the controlled server identity and parses pagination", async () => {
    server.use(
      http.get("http://api.test/api/v1/clinical-cases", ({ request }) => {
        expect(request.headers.get("x-development-identity")).toBe("physician");
        return HttpResponse.json(
          { items: [], page: 1, page_size: 25, total: 0 },
          { headers: { "x-correlation-id": "corr" } },
        );
      }),
    );
    const client = new VinamiApiClient({
      baseUrl: "http://api.test",
      developmentIdentity: "physician",
    });
    await expect(client.listClinicalCases()).resolves.toMatchObject({
      total: 0,
    });
  });

  it("sends typed R2 commands with a stable idempotency key", async () => {
    const caseId = "10000000-0000-4000-8000-000000000001";
    server.use(
      http.post(
        `http://api.test/api/v1/clinical-cases/${caseId}/triage-assessments`,
        async ({ request }) => {
          expect(request.headers.get("idempotency-key")).toBe("stable-r2-key");
          expect(await request.json()).toMatchObject({
            expected_case_version: 1,
            symptom_onset_state: "not_assessed",
          });
          return HttpResponse.json(
            {
              assessment_id: "20000000-0000-4000-8000-000000000001",
              clinical_case_id: caseId,
              revision_number: 1,
              status: "recorded",
              source: "test",
              recorded_by_actor_id: "30000000-0000-4000-8000-000000000001",
              recorded_by_actor_role: "nurse",
              occurred_at: "2026-07-14T08:00:00Z",
              recorded_at: "2026-07-14T08:00:01Z",
              correlation_id: "40000000-0000-4000-8000-000000000001",
              causation_id: null,
              record_version: 1,
              chief_complaint: null,
              symptom_onset_state: "not_assessed",
              symptom_onset_at: null,
              symptom_onset_precision: null,
              symptom_description: null,
              symptom_location: null,
              symptom_radiation: null,
              symptom_duration: null,
              symptom_pattern: null,
              aggravating_factors: null,
              relieving_factors: null,
              relevant_history_summary: null,
              current_medication_summary: null,
              allergy_summary: null,
              clinical_note: null,
              associated_symptoms: [],
              cardiovascular_risk_factors: [],
              corrects_assessment_id: null,
              correction_reason: null,
            },
            { status: 201 },
          );
        },
      ),
    );
    const client = new VinamiApiClient({ baseUrl: "http://api.test" });
    await expect(
      client.recordTriage(
        caseId,
        {
          expected_case_version: 1,
          occurred_at: "2026-07-14T08:00:00Z",
          source: "test",
          symptom_onset_state: "not_assessed",
          associated_symptoms: [],
          cardiovascular_risk_factors: [],
        },
        "stable-r2-key",
      ),
    ).resolves.toMatchObject({ revision_number: 1 });
  });

  it.each([401, 403, 404, 409, 422, 500])(
    "maps HTTP %s without leaking routes",
    async (status) => {
      server.use(
        http.get("http://api.test/api/v1/identity/session", () =>
          HttpResponse.json(
            {
              type: "urn:test",
              title: "Failure",
              status,
              detail: "Safe detail",
              instance: "/hidden",
              correlation_id: "corr",
            },
            { status, headers: { "content-type": "application/problem+json" } },
          ),
        ),
      );
      const client = new VinamiApiClient({ baseUrl: "http://api.test" });
      await expect(client.getIdentitySession()).rejects.toBeInstanceOf(
        VinamiApiError,
      );
    },
  );
});
