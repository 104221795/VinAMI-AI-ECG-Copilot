import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

const api = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";
const clinicalTime = "2026-07-16T08:00:00Z";

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r8",
  };
}

async function createR8Case(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patientReference = `R8-SYN-${suffix}`;
  const patient = await request.post(`${api}/api/v1/patients`, {
    headers: headers(`r8-patient-${suffix}`, "nurse"),
    data: { patient_reference: patientReference, safe_demographic_summary: {} },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${api}/api/v1/encounters`, {
    headers: headers(`r8-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Emergency Department",
      arrival_at: clinicalTime,
    },
  });
  const clinicalCase = await request.post(`${api}/api/v1/clinical-cases`, {
    headers: headers(`r8-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "Synthetic R8 integrated case review",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  const caseValue = await clinicalCase.json();
  const caseId = caseValue.case_id as string;
  const version = caseValue.aggregate_version as number;

  const triage = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/triage-assessments`,
    {
      headers: headers(`r8-triage-${suffix}`, "nurse"),
      data: {
        expected_case_version: version,
        occurred_at: clinicalTime,
        source: "playwright-r8",
        chief_complaint: "R8 synthetic chest discomfort",
        symptom_onset_state: "unknown",
        associated_symptoms: [],
        cardiovascular_risk_factors: [],
      },
    },
  );
  expect(triage.status(), await triage.text()).toBe(201);
  const vitals = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/vital-observation-sets`,
    {
      headers: headers(`r8-vitals-${suffix}`, "nurse"),
      data: {
        expected_case_version: version,
        observed_at: "2026-07-16T08:02:00Z",
        source: "playwright-r8",
        supplemental_oxygen_state: "not_assessed",
        measurements: [
          {
            kind: "heart_rate",
            value: 82,
            unit: "beats/min",
            source: "manual-entry",
            observed_at: "2026-07-16T08:02:00Z",
            quality_status: "accepted",
          },
        ],
      },
    },
  );
  expect(vitals.status(), await vitals.text()).toBe(201);
  for (const [minute, value] of [
    [10, "10.00"],
    [25, "12.40"],
  ] as const) {
    const result = await request.post(
      `${api}/api/v1/clinical-cases/${caseId}/troponin-results`,
      {
        headers: headers(`r8-trop-${minute}-${suffix}`),
        data: {
          assay_code: "DEMO-HS-CTNI-01",
          analyte: "cardiac_troponin_i",
          value,
          unit: "ng/L",
          specimen_type: "plasma",
          specimen_collected_at: `2026-07-16T08:${minute}:00Z`,
          resulted_at: `2026-07-16T08:${minute + 1}:00Z`,
          result_status: "final",
          quality_flags: [],
          source_system: "playwright-r8",
          source_result_id: `r8-${minute}-${suffix}`,
          expected_case_version: version,
        },
      },
    );
    expect(result.status(), await result.text()).toBe(201);
  }
  const snapshot = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/clinical-reasoning/snapshots`,
    {
      headers: headers(`r8-snapshot-${suffix}`),
      data: { expected_case_version: version },
    },
  );
  const snapshotValue = await snapshot.json();
  const assessment = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/clinical-reasoning/assessments`,
    {
      headers: headers(`r8-assessment-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        expected_snapshot_version: 1,
        summary: "R8 physician integrated assessment.",
        supporting_evidence: ["clinical_case:v1"],
        contradictory_evidence: [],
        uncertainty: "Further physician review remains required.",
      },
    },
  );
  const assessmentValue = await assessment.json();
  const decision = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/clinical-reasoning/decisions`,
    {
      headers: headers(`r8-decision-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        assessment_id: assessmentValue.assessment_id,
        expected_snapshot_version: 1,
        expected_assessment_version: 1,
        decision_type: "request_repeat_ecg",
        rationale: "R8 physician requested repeat ECG review.",
        uncertainty: "This is not a diagnosis or treatment instruction.",
        evidence_references: ["clinical_case:v1"],
      },
    },
  );
  const decisionValue = await decision.json();
  const workflow = await request.get(
    `${api}/api/v1/clinical-cases/${caseId}/workflow-operations`,
    { headers: headers(`r8-workflow-${suffix}`) },
  );
  const task = await request.post(
    `${api}/api/v1/clinical-cases/${caseId}/workflow-operations/tasks/from-decisions`,
    {
      headers: headers(`r8-task-${suffix}`),
      data: {
        decision_id: decisionValue.decision_id,
        expected_decision_version: decisionValue.record_version,
        expected_workflow_version: (await workflow.json()).workflow.version,
        priority: "urgent",
        due_at: null,
      },
    },
  );
  expect(task.status(), await task.text()).toBe(201);
  return { caseId, patientReference };
}

test("R8 reviews the integrated case and preserves context across workspaces", async ({
  page,
  request,
}) => {
  const value = await createR8Case(request);
  await page.goto(`/cases/${value.caseId}`);
  await expect(
    page.getByRole("heading", { name: value.patientReference }),
  ).toBeVisible();
  for (const heading of [
    "Triage and latest vitals",
    "ECG evidence",
    "Serial troponin",
    "Clinical reasoning and physician authority",
    "Workflow state",
    "Active tasks and unresolved alerts",
    "Recent Timeline",
  ]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(page.getByText("R8 synthetic chest discomfort")).toBeVisible();
  await expect(
    page.getByText("Current non-revoked physician decision"),
  ).toBeVisible();
  await expect(page.getByText("Missing: ecg.")).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .include("main")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);

  await page.getByRole("link", { name: "Open Clinical Reasoning" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/cases/${value.caseId}/clinical-reasoning$`),
  );
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`/cases/${value.caseId}$`));
  await expect(
    page.getByRole("heading", { name: value.patientReference }),
  ).toBeVisible();
});

test("R8 refreshes an owning-workspace task update without duplicating history", async ({
  page,
  request,
}) => {
  const value = await createR8Case(request);
  await page.goto(`/cases/${value.caseId}`);
  await expect(page.getByText("1").first()).toBeVisible();
  await page.getByRole("link", { name: "Manage in Workflow" }).click();
  await page.getByRole("button", { name: "Assign" }).click();
  await page
    .getByRole("dialog", { name: "Assign task" })
    .getByRole("button", { name: "Confirm assign" })
    .click();
  for (const action of ["Acknowledge", "Start"]) {
    await page.getByRole("button", { name: action }).click();
    await page
      .getByRole("dialog", { name: `${action} task` })
      .getByRole("button", { name: `Confirm ${action.toLowerCase()}` })
      .click();
  }
  await page.getByRole("button", { name: "Complete" }).click();
  const dialog = page.getByRole("dialog", { name: "Complete task" });
  await dialog
    .getByLabel("Required reason")
    .fill("R8 owning workspace completion.");
  await dialog.getByRole("button", { name: "Confirm complete" }).click();
  await page.goto(`/cases/${value.caseId}`);
  await expect(
    page.getByText("No active tasks or unresolved alerts"),
  ).toBeVisible();
  await expect(
    page.getByText("R8 physician requested repeat ECG review."),
  ).toHaveCount(1);
});
