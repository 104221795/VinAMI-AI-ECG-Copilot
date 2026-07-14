import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import path from "node:path";

const apiBase = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";
const completeCase = "0390099f-e465-5720-8099-47ce6e76109e";
const incompleteCase = "9aa21eab-1f59-58bf-bb46-7b8e2c3a9036";
const correctedCase = "f934591c-28e6-5889-8959-316e9fee9310";
const screenshots = path.resolve(process.cwd(), "docs/frontend/screenshots");
const now = "2026-07-14T03:15:00.000Z";

type ClinicalCase = {
  case_id: string;
  aggregate_version: number;
};

type TriageAssessment = {
  assessment_id: string;
  record_version: number;
  revision_number: number;
};

type VitalObservationSet = {
  vital_set_id: string;
  record_version: number;
  revision_number: number;
  sequence_number: number;
};

function commandHeaders(key: string, identity = "nurse") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r2",
  };
}

function readHeaders(identity = "physician") {
  return {
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r2",
  };
}

async function createCase(
  request: APIRequestContext,
  label: string,
): Promise<ClinicalCase> {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patient = await request.post(`${apiBase}/api/v1/patients`, {
    headers: commandHeaders(`r2-${label}-patient-${suffix}`),
    data: {
      patient_reference: `R2-E2E-${label}-${suffix}`,
      safe_demographic_summary: {
        age_band: "45-64",
        sex_at_birth: "synthetic",
      },
    },
  });
  expect(patient.status(), await patient.text()).toBe(201);

  const patientBody = await patient.json();
  const encounter = await request.post(`${apiBase}/api/v1/encounters`, {
    headers: commandHeaders(`r2-${label}-encounter-${suffix}`),
    data: {
      patient_id: patientBody.patient_id,
      location: "Emergency Department",
      arrival_at: now,
      external_reference: `R2-E2E-ENC-${label}-${suffix}`,
    },
  });
  expect(encounter.status(), await encounter.text()).toBe(201);

  const encounterBody = await encounter.json();
  const clinicalCase = await request.post(`${apiBase}/api/v1/clinical-cases`, {
    headers: commandHeaders(`r2-${label}-case-${suffix}`),
    data: {
      encounter_id: encounterBody.encounter_id,
      opening_reason: `R2.1 Playwright ${label}`,
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  return (await clinicalCase.json()) as ClinicalCase;
}

function triagePayload(caseVersion: number, complaint: string) {
  return {
    expected_case_version: caseVersion,
    occurred_at: now,
    source: "playwright-r2-triage",
    chief_complaint: complaint,
    symptom_description: "E2E structured symptom description",
    symptom_onset_state: "present",
    symptom_onset_at: "2026-07-14T02:30:00.000Z",
    symptom_onset_precision: "approximate",
    associated_symptoms: [
      { name: "dyspnoea", state: "present", note: null },
      { name: "nausea", state: "absent", note: null },
    ],
    cardiovascular_risk_factors: [
      { name: "smoking history", state: "unknown", note: null },
      { name: "diabetes history", state: "not_assessed", note: null },
    ],
  };
}

function vitalPayload(caseVersion: number, value: number, observedAt: string) {
  return {
    expected_case_version: caseVersion,
    observed_at: observedAt,
    source: "playwright-r2-vitals",
    supplemental_oxygen_state: "not_assessed",
    measurements: [
      {
        kind: "heart_rate",
        value,
        unit: "beats/min",
        source: "playwright-r2-vitals",
        observed_at: observedAt,
        quality_status: "accepted",
      },
      {
        kind: "systolic_blood_pressure",
        value: 120,
        unit: "mmHg",
        source: "playwright-r2-vitals",
        observed_at: observedAt,
        quality_status: "accepted",
      },
    ],
  };
}

async function recordTriage(
  request: APIRequestContext,
  clinicalCase: ClinicalCase,
  key: string,
  complaint = "R2.1 direct triage seed",
): Promise<TriageAssessment> {
  const response = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage-assessments`,
    {
      headers: commandHeaders(key),
      data: triagePayload(clinicalCase.aggregate_version, complaint),
    },
  );
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as TriageAssessment;
}

async function recordVitals(
  request: APIRequestContext,
  clinicalCase: ClinicalCase,
  key: string,
  value: number,
  observedAt = "2026-07-14T03:20:00.000Z",
): Promise<VitalObservationSet> {
  const response = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/vital-observation-sets`,
    {
      headers: commandHeaders(key),
      data: vitalPayload(clinicalCase.aggregate_version, value, observedAt),
    },
  );
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as VitalObservationSet;
}

async function waitForProjection(
  request: APIRequestContext,
  caseId: string,
  eventType: string,
) {
  await expect
    .poll(
      async () => {
        const timeline = await request.get(
          `${apiBase}/api/v1/clinical-cases/${caseId}/timeline`,
          { headers: readHeaders() },
        );
        if (!timeline.ok()) return "";
        const events = (await timeline.json()) as Array<{ event_type: string }>;
        return events.map((event) => event.event_type).join(",");
      },
      { timeout: 15_000 },
    )
    .toContain(eventType);
  await expect
    .poll(
      async () => {
        const audit = await request.get(
          `${apiBase}/api/v1/clinical-cases/${caseId}/audit`,
          {
            headers: readHeaders("auditor"),
          },
        );
        if (!audit.ok()) return "";
        const entries = (await audit.json()) as Array<{
          action: string;
          actor_role: string | null;
          correlation_id: string;
        }>;
        return entries
          .map(
            (entry) =>
              `${entry.action}:${entry.actor_role}:${entry.correlation_id}`,
          )
          .join(",");
      },
      { timeout: 15_000 },
    )
    .toContain(`event:${eventType}`);
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
    .analyze();
  expect(
    results.violations,
    results.violations.map((item) => `${item.id}: ${item.help}`).join("\n"),
  ).toEqual([]);
}

async function submitTriageForm(page: Page, complaint: string) {
  await page.getByRole("button", { name: "Record triage" }).click();
  await page.getByLabel("Chief complaint").fill(complaint);
  await page
    .getByLabel("Patient-reported symptom description")
    .fill("E2E structured symptom details");
  await page.getByLabel("Symptom onset status").selectOption("present");
  await page.getByLabel("Reported onset time").fill("2026-07-14T09:30");
  await page.getByLabel("Time precision").selectOption("approximate");
  await page.getByLabel("Dyspnoea").selectOption("present");
  await page.getByLabel("Nausea").selectOption("absent");
  await page.getByLabel("Smoking history").selectOption("unknown");
  await page.getByLabel("Diabetes history").selectOption("not_assessed");
  await page.getByRole("button", { name: "Review entry" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record triage" })
    .click();
  await expect(page.getByText("Triage assessment recorded.")).toBeVisible();
}

async function submitVitalForm(
  page: Page,
  heartRate: string,
  observedAt: string,
) {
  await page.getByRole("button", { name: "Record new set" }).click();
  await page.getByLabel("Observation time").fill(observedAt);
  await page.getByLabel("Heart rate").fill(heartRate);
  await page.getByLabel("Systolic BP").fill("120");
  await page.getByRole("button", { name: "Review vital set" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record vital set" })
    .click();
  await expect(page.getByText("Vital observation set recorded.")).toBeVisible();
}

test("R2 complete documentation renders persisted provenance", async ({
  page,
}, testInfo) => {
  await page.goto(`/cases/${completeCase}`);
  await expect(
    page.getByRole("heading", { name: "Triage and vital documentation" }),
  ).toBeVisible();
  await expect(page.getByText("Documentation policy complete")).toBeVisible();
  await expect(
    page.getByText("Synthetic chest discomfort documentation"),
  ).toBeVisible();
  await expect(page.getByText("beats/min")).toBeVisible();
  await expect(page.getByText("Backend policy")).toHaveCount(0);
  await expect(
    page.getByText(/No diagnosis, pathway, or clinical threshold is inferred/),
  ).toBeVisible();

  const body = await page.locator("body").innerText();
  expect(body.toLowerCase()).not.toContain("normal vital");
  expect(body.toLowerCase()).not.toContain("abnormal vital");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(await page.evaluate(() => window.innerWidth));
  await expectAccessible(page);
  await page.screenshot({
    path: path.join(
      screenshots,
      `r2-case-workspace-${testInfo.project.name}.png`,
    ),
    fullPage: true,
  });
});

test("Scenario A records triage through the UI and projects timeline/audit", async ({
  page,
  request,
}) => {
  const clinicalCase = await createCase(request, "record-triage");
  const complaint = `R2.1 UI triage ${crypto.randomUUID()}`;

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await submitTriageForm(page, complaint);
  await page.reload();

  await expect(page.getByText(complaint)).toBeVisible();
  await expect(
    page.getByText("Revision 1", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("present").first()).toBeVisible();
  await expect(page.getByText("absent").first()).toBeVisible();
  await expect(page.getByText("unknown").first()).toBeVisible();
  await expect(page.getByText("not assessed").first()).toBeVisible();
  await waitForProjection(
    request,
    clinicalCase.case_id,
    "TriageAssessmentRecorded.v1",
  );
  await page.goto(`/cases/${clinicalCase.case_id}/timeline`);
  await expect(
    page.getByText("Triage assessment recorded").first(),
  ).toBeVisible();
  await expect(
    page.locator("dd", { hasText: "TriageAssessmentRecorded.v1" }),
  ).toHaveCount(1);
  await page.goto(`/cases/${clinicalCase.case_id}/audit`);
  await expect(
    page.getByText("event:TriageAssessmentRecorded.v1"),
  ).toBeVisible();
  await expect(page.getByText("playwright-r2").first()).toBeVisible();
});

test("Scenario B records repeated vitals through the UI", async ({
  page,
  request,
}) => {
  const clinicalCase = await createCase(request, "record-vitals");

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await submitVitalForm(page, "72", "2026-07-14T10:00");
  await submitVitalForm(page, "78", "2026-07-14T10:15");
  await page.reload();

  await expect(page.getByText("78 beats/min")).toBeVisible();
  await expect(page.getByText("beats/min").first()).toBeVisible();
  await expect(page.getByText("Set 2", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Set 1", { exact: true }).first()).toBeVisible();
  await waitForProjection(
    request,
    clinicalCase.case_id,
    "VitalObservationSetRecorded.v1",
  );
  await page.goto(`/cases/${clinicalCase.case_id}/timeline`);
  await expect(
    page.locator("dd", { hasText: "VitalObservationSetRecorded.v1" }),
  ).not.toHaveCount(0);
  await page.goto(`/cases/${clinicalCase.case_id}/audit`);
  await expect(
    page.getByText("event:VitalObservationSetRecorded.v1").first(),
  ).toBeVisible();
});

test("Scenario C corrects triage while preserving the original revision", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Correction journey runs once on desktop",
  );
  const clinicalCase = await createCase(request, "correct-triage");
  await recordTriage(
    request,
    clinicalCase,
    `r2-correct-triage-seed-${crypto.randomUUID()}`,
  );

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await page.getByRole("button", { name: "Correct entry" }).click();
  await expect(
    page.getByRole("button", { name: "Review correction" }),
  ).toBeDisabled();
  await page
    .getByLabel("Chief complaint")
    .fill("R2.1 corrected triage complaint");
  await page.getByLabel("Correction reason").fill("E2E correction reason");
  await page.getByRole("button", { name: "Review correction" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record correction" })
    .click();
  await expect(
    page.getByText("Triage correction recorded as a new revision."),
  ).toBeVisible();
  await page.reload();

  await expect(page.getByText("R2.1 corrected triage complaint")).toBeVisible();
  await expect(
    page.getByText("Revision 2", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Revision 1", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Correction reason:")).toBeVisible();
  await waitForProjection(
    request,
    clinicalCase.case_id,
    "TriageAssessmentCorrected.v1",
  );
});

test("Scenario D corrects vitals while preserving history", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Correction journey runs once on desktop",
  );
  const clinicalCase = await createCase(request, "correct-vitals");
  await recordVitals(
    request,
    clinicalCase,
    `r2-correct-vitals-seed-${crypto.randomUUID()}`,
    73,
  );

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await page.getByRole("button", { name: "Correct latest" }).click();
  await expect(
    page.getByRole("button", { name: "Review correction" }),
  ).toBeDisabled();
  await page.getByLabel("Heart rate").fill("76");
  await page
    .getByLabel("Correction reason")
    .fill("E2E vital source correction");
  await page.getByRole("button", { name: "Review correction" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record correction" })
    .click();
  await expect(
    page.getByText("Vital correction recorded as a new revision."),
  ).toBeVisible();
  await page.reload();

  await expect(page.getByText("76 beats/min")).toBeVisible();
  await expect(
    page.getByText("Revision 2", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Revision 1", { exact: true }).first(),
  ).toBeVisible();
  await waitForProjection(
    request,
    clinicalCase.case_id,
    "VitalObservationSetCorrected.v1",
  );
});

test("Scenario E stale concurrency is handled without silent overwrite", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Concurrency journey runs once on desktop",
  );
  const clinicalCase = await createCase(request, "stale");
  const initial = await recordTriage(
    request,
    clinicalCase,
    `r2-stale-seed-${crypto.randomUUID()}`,
    "Initial stale test triage",
  );
  const correctionBody = {
    ...triagePayload(
      clinicalCase.aggregate_version,
      "Server-side current correction",
    ),
    expected_record_version: initial.record_version,
    correction_reason: "Session A committed first",
  };
  delete (correctionBody as { expected_case_version?: number })
    .expected_case_version;
  const sessionA = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage-assessments/${initial.assessment_id}/corrections`,
    {
      headers: commandHeaders(`r2-stale-session-a-${crypto.randomUUID()}`),
      data: correctionBody,
    },
  );
  expect(sessionA.status(), await sessionA.text()).toBe(201);

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await page.route("**/api/backend/**/corrections", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://vinami.example/problems/stale-record",
        title: "Stale record version",
        status: 409,
        detail:
          "The record changed while it was being read. Refresh before continuing.",
        instance: "r2-e2e-stale",
        correlation_id: "11111111-1111-4111-8111-111111111111",
      }),
    });
  });
  await page.getByRole("button", { name: "Correct entry" }).click();
  await page.getByLabel("Chief complaint").fill("Session B stale draft");
  await page
    .getByLabel("Correction reason")
    .fill("Session B attempts stale update");
  await page.getByRole("button", { name: "Review correction" }).click();
  const staleResponse = page.waitForResponse(
    (response) =>
      response.url().includes("/corrections") && response.status() === 409,
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record correction" })
    .click();
  await staleResponse;
  await expect(page.getByText("Refresh before continuing")).toBeVisible();
  await expect(page.getByLabel("Chief complaint")).toHaveValue(
    "Session B stale draft",
  );
  await page.unroute("**/api/backend/**/corrections");
  await page.reload();
  await expect(page.getByText("Server-side current correction")).toBeVisible();
  await expect(page.getByText("Session B stale draft")).toHaveCount(0);
});

test("Scenario F duplicate submission reuses idempotency and persists once", async ({
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Idempotency journey runs once on desktop",
  );
  const clinicalCase = await createCase(request, "duplicate");
  const key = `r2-duplicate-${crypto.randomUUID()}`;
  const body = triagePayload(
    clinicalCase.aggregate_version,
    "R2.1 duplicate-safe triage",
  );
  const first = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage-assessments`,
    { headers: commandHeaders(key), data: body },
  );
  const second = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage-assessments`,
    { headers: commandHeaders(key), data: body },
  );
  expect(first.status(), await first.text()).toBe(201);
  expect(second.status(), await second.text()).toBe(201);
  const firstBody = (await first.json()) as TriageAssessment;
  const secondBody = (await second.json()) as TriageAssessment;
  expect(secondBody.assessment_id).toBe(firstBody.assessment_id);

  const history = await request.get(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage/history`,
    { headers: readHeaders() },
  );
  expect(history.status(), await history.text()).toBe(200);
  expect((await history.json()).total).toBe(1);
  await waitForProjection(
    request,
    clinicalCase.case_id,
    "TriageAssessmentRecorded.v1",
  );
});

test("Scenario G validation and permission failures are controlled", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Validation journey runs once on desktop",
  );
  const clinicalCase = await createCase(request, "validation");
  await recordTriage(
    request,
    clinicalCase,
    `r2-validation-triage-${crypto.randomUUID()}`,
  );

  await page.goto(`/cases/${clinicalCase.case_id}`);
  await page.getByRole("button", { name: "Record new set" }).click();
  await page.getByRole("button", { name: "Review vital set" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record vital set" })
    .click();
  await expect(
    page.getByText("Enter at least one vital observation before review."),
  ).toBeVisible();

  const invalidUnit = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/vital-observation-sets`,
    {
      headers: commandHeaders(`r2-invalid-unit-${crypto.randomUUID()}`),
      data: {
        ...vitalPayload(
          clinicalCase.aggregate_version,
          72,
          "2026-07-14T03:35:00.000Z",
        ),
        measurements: [
          {
            kind: "heart_rate",
            value: 72,
            unit: "bpm",
            source: "playwright-r2-vitals",
            observed_at: "2026-07-14T03:35:00.000Z",
            quality_status: "accepted",
          },
        ],
      },
    },
  );
  expect(invalidUnit.status()).toBe(400);

  const forbidden = await request.post(
    `${apiBase}/api/v1/clinical-cases/${clinicalCase.case_id}/triage-assessments`,
    {
      headers: commandHeaders(
        `r2-forbidden-${crypto.randomUUID()}`,
        "read_only_reviewer",
      ),
      data: triagePayload(
        clinicalCase.aggregate_version,
        "Forbidden write attempt",
      ),
    },
  );
  expect(forbidden.status()).toBe(403);
  expect(await forbidden.text()).not.toContain("Traceback");
});

test("R2 correction remains explicit and opens an append-only form", async ({
  page,
}) => {
  await page.goto(`/cases/${correctedCase}`);
  await expect(
    page.getByText("Synthetic clarified symptom wording"),
  ).toBeVisible();
  await expect(page.getByText("Correction reason:").first()).toBeVisible();
  await expect(
    page.getByText("Revision 2", { exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Correct entry" }).click();
  await expect(
    page.getByText("Correction reason", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review correction" }),
  ).toBeVisible();
  await expect(page.getByText("Time precision")).toHaveCount(0);
  await expectAccessible(page);
});

test("R2 BFF allows only documented command paths and preserves problem responses", async ({
  request,
}) => {
  const response = await request.post(
    `/api/backend/api/v1/clinical-cases/${completeCase}/vital-observation-sets`,
    {
      headers: { "Idempotency-Key": "r2-e2e-invalid-contract" },
      data: { expected_case_version: 1 },
    },
  );
  expect(response.status()).toBe(422);
  expect(response.headers()["content-type"]).toContain(
    "application/problem+json",
  );
  const blocked = await request.post("/api/backend/api/v1/model-registry", {
    data: {},
  });
  expect(blocked.status()).toBe(404);
});

test("R2 visual-state baselines cover documentation workflows", async ({
  page,
  request,
}, testInfo) => {
  const project = testInfo.project.name;
  const capture = async (name: string) => {
    await page.screenshot({
      path: path.join(screenshots, `r2-${name}-${project}.png`),
      fullPage: true,
      animations: "disabled",
    });
  };

  const emptyCase = await createCase(request, `visual-empty-${project}`);
  await page.goto(`/cases/${emptyCase.case_id}`);
  await expect(page.getByText("No triage assessment recorded")).toBeVisible();
  await capture("empty-triage-state");

  await page.goto(`/cases/${completeCase}`);
  await expect(page.getByText("Documentation policy complete")).toBeVisible();
  await capture("completed-triage-summary");
  if (project === "desktop") {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.reload();
    await capture("complete-clinical-case-workspace-1920");
    await page.setViewportSize({ width: 1440, height: 900 });
  }

  await page.goto(`/cases/${incompleteCase}`);
  await expect(
    page.getByText("Documentation completeness review"),
  ).toBeVisible();
  await capture("incomplete-documentation-summary");

  await page.goto(`/cases/${emptyCase.case_id}`);
  await page.getByRole("button", { name: "Record triage" }).click();
  await expect(page.getByLabel("Chief complaint")).toBeVisible();
  await capture("triage-entry-form");

  const triageVisualCase = await createCase(
    request,
    `visual-triage-${project}`,
  );
  await recordTriage(
    request,
    triageVisualCase,
    `r2-visual-triage-${project}-${crypto.randomUUID()}`,
  );
  await page.goto(`/cases/${triageVisualCase.case_id}`);
  await page.getByRole("button", { name: "Correct entry" }).click();
  await expect(
    page.getByRole("button", { name: "Review correction" }),
  ).toBeDisabled();
  await capture("triage-validation-errors");

  const vitalVisualCase = await createCase(request, `visual-vitals-${project}`);
  await recordVitals(
    request,
    vitalVisualCase,
    `r2-visual-vitals-1-${project}-${crypto.randomUUID()}`,
    72,
    "2026-07-14T03:20:00.000Z",
  );
  await recordVitals(
    request,
    vitalVisualCase,
    `r2-visual-vitals-2-${project}-${crypto.randomUUID()}`,
    78,
    "2026-07-14T03:35:00.000Z",
  );
  await page.goto(`/cases/${vitalVisualCase.case_id}`);
  await expect(page.getByText("78 beats/min")).toBeVisible();
  await capture("latest-vital-observations");
  await expect(page.getByText("Set 1", { exact: true }).first()).toBeVisible();
  await capture("repeated-vitals-history");

  await page.goto(`/cases/${correctedCase}`);
  await page.getByRole("button", { name: "Correct entry" }).click();
  await page
    .getByLabel("Correction reason")
    .fill("Visual triage correction confirmation");
  await page.getByRole("button", { name: "Review correction" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await capture("triage-correction-confirmation");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel" })
    .click();

  await page.getByRole("button", { name: "Correct latest" }).click();
  await page
    .getByLabel("Correction reason")
    .fill("Visual vital correction confirmation");
  await page.getByRole("button", { name: "Review correction" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await capture("vital-correction-confirmation");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel" })
    .click();

  await page.goto(`/cases/${triageVisualCase.case_id}`);
  await page.route("**/api/backend/**/corrections", async (route) => {
    await route.fulfill({
      status: 409,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://vinami.example/problems/stale-record",
        title: "Stale record version",
        status: 409,
        detail:
          "The record changed while it was being read. Refresh before continuing.",
        instance: "r2-visual-stale",
        correlation_id: "22222222-2222-4222-8222-222222222222",
      }),
    });
  });
  await page.getByRole("button", { name: "Correct entry" }).click();
  await page.getByLabel("Correction reason").fill("Visual stale correction");
  await page.getByRole("button", { name: "Review correction" }).click();
  const visualStale = page.waitForResponse(
    (response) =>
      response.url().includes("/corrections") && response.status() === 409,
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record correction" })
    .click();
  await visualStale;
  await expect(page.getByText("Refresh before continuing")).toBeVisible();
  await capture("stale-version-conflict");
  await page.unroute("**/api/backend/**/corrections");

  await page.goto(`/cases/${emptyCase.case_id}`);
  await page.route("**/api/backend/**/triage-assessments", async (route) => {
    await route.fulfill({
      status: 403,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://vinami.example/problems/permission-denied",
        title: "Permission denied",
        status: 403,
        detail:
          "Your verified identity does not have permission to write triage documentation.",
        instance: "r2-visual-permission",
        correlation_id: "33333333-3333-4333-8333-333333333333",
      }),
    });
  });
  await page.getByRole("button", { name: "Record triage" }).click();
  await page
    .getByLabel("Chief complaint")
    .fill("Permission-denied visual state");
  await page.getByRole("button", { name: "Review entry" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record triage" })
    .click();
  await expect(page.getByText("does not have permission")).toBeVisible();
  await capture("permission-denied-state");
  await page.unroute("**/api/backend/**/triage-assessments");

  await page.goto(`/cases/${emptyCase.case_id}`);
  await page.route("**/api/backend/**/triage-assessments", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://vinami.example/problems/upstream-unavailable",
        title: "Upstream unavailable",
        status: 503,
        detail: "The clinical service could not be reached.",
        instance: "r2-visual-offline",
        correlation_id: "44444444-4444-4444-8444-444444444444",
      }),
    });
  });
  await page.getByRole("button", { name: "Record triage" }).click();
  await page.getByLabel("Chief complaint").fill("Offline visual state");
  await page.getByRole("button", { name: "Review entry" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record triage" })
    .click();
  await expect(page.getByText("could not be reached")).toBeVisible();
  await capture("offline-api-unavailable-state");
  await page.unroute("**/api/backend/**/triage-assessments");

  await page.goto("/command-center");
  await page.route("**/api/backend/api/v1/clinical-cases?**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 900));
    await route.continue();
  });
  await page.getByLabel("Priority").selectOption("urgent");
  await capture("loading-state");
});
