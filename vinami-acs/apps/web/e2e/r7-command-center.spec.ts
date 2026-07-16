import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

const api = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r7",
  };
}

async function createOperationalCase(
  request: APIRequestContext,
  dueAt?: string,
) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patientReference = `R7-SYN-${suffix}`;
  const patient = await request.post(`${api}/api/v1/patients`, {
    headers: headers(`r7-patient-${suffix}`, "nurse"),
    data: { patient_reference: patientReference, safe_demographic_summary: {} },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${api}/api/v1/encounters`, {
    headers: headers(`r7-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Emergency Department",
      arrival_at: "2026-07-15T08:00:00Z",
    },
  });
  const clinicalCase = await request.post(`${api}/api/v1/clinical-cases`, {
    headers: headers(`r7-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "Synthetic R7 operational queue scenario",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  const caseValue = await clinicalCase.json();
  const snapshot = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/clinical-reasoning/snapshots`,
    {
      headers: headers(`r7-snapshot-${suffix}`),
      data: { expected_case_version: caseValue.aggregate_version },
    },
  );
  const snapshotValue = await snapshot.json();
  const assessment = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/clinical-reasoning/assessments`,
    {
      headers: headers(`r7-assessment-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        expected_snapshot_version: 1,
        summary: "Physician assessment for R7 operational follow-up.",
        supporting_evidence: ["clinical_case:v1"],
        contradictory_evidence: [],
        uncertainty: "Further human review remains required.",
      },
    },
  );
  const assessmentValue = await assessment.json();
  const decision = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/clinical-reasoning/decisions`,
    {
      headers: headers(`r7-decision-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        assessment_id: assessmentValue.assessment_id,
        expected_snapshot_version: 1,
        expected_assessment_version: 1,
        decision_type: "request_repeat_ecg",
        rationale: "Physician requested repeat ECG operational review.",
        uncertainty: "This is not a diagnosis or treatment instruction.",
        evidence_references: ["clinical_case:v1"],
      },
    },
  );
  const decisionValue = await decision.json();
  const workspace = await request.get(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/workflow-operations`,
    { headers: headers(`r7-workspace-${suffix}`) },
  );
  const task = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/workflow-operations/tasks/from-decisions`,
    {
      headers: headers(`r7-task-${suffix}`),
      data: {
        decision_id: decisionValue.decision_id,
        expected_decision_version: decisionValue.record_version,
        expected_workflow_version: (await workspace.json()).workflow.version,
        priority: "urgent",
        due_at: dueAt ?? null,
      },
    },
  );
  expect(task.status(), await task.text()).toBe(201);
  if (dueAt) {
    const evaluated = await request.post(
      `${api}/api/v1/clinical-cases/${caseValue.case_id}/workflow-operations/overdue-evaluations`,
      { headers: headers(`r7-overdue-${suffix}`), data: {} },
    );
    expect(evaluated.status(), await evaluated.text()).toBe(200);
  }
  return {
    caseId: caseValue.case_id as string,
    patientReference,
  };
}

test("R7 filters, selects and opens an authoritative case view", async ({
  page,
  request,
}) => {
  const value = await createOperationalCase(request, "2020-01-01T00:00:00Z");
  await page.goto("/command-center");
  await page
    .locator("label", { hasText: /^Operational priority/ })
    .locator("select")
    .selectOption("critical");
  await page
    .locator("label", { hasText: /^Due state/ })
    .locator("select")
    .selectOption("true");
  await page
    .locator("label", { hasText: /^Sort by/ })
    .locator("select")
    .selectOption("next_due_at");
  await expect(page.getByText(value.patientReference)).toBeVisible();
  await page
    .getByRole("row", { name: new RegExp(value.patientReference) })
    .click();

  const quickView = page.getByRole("complementary", {
    name: "Selected case quick view",
  });
  await expect(quickView.getByText("Physician decision")).toBeVisible();
  await expect(quickView.getByText("Evidence status")).toBeVisible();
  await expect(
    quickView.getByText("Repeat Ecg", { exact: true }),
  ).toBeVisible();
  await expect(quickView.getByText("Task Overdue")).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .include("main")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);

  await quickView.getByRole("link", { name: "Clinical Reasoning" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/cases/${value.caseId}/clinical-reasoning$`),
  );
});

test("R7 reflects a completed R6 task without duplicate queue records", async ({
  page,
  request,
}) => {
  const value = await createOperationalCase(request);
  await page.goto(`/cases/${value.caseId}/workflow`);
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
  const completion = page.getByRole("dialog", { name: "Complete task" });
  await completion
    .getByLabel("Required reason")
    .fill("R7 projection verification completion.");
  await completion.getByRole("button", { name: "Confirm complete" }).click();

  await page.goto("/command-center");
  await expect(page.getByText(value.patientReference)).toHaveCount(1);
  await page
    .getByRole("row", { name: new RegExp(value.patientReference) })
    .click();
  const quickView = page.getByRole("complementary", {
    name: "Selected case quick view",
  });
  await expect(
    quickView.getByText("No active operational task."),
  ).toBeVisible();
});
