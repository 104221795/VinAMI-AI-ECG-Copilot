import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

const api = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r6",
  };
}

async function createCaseAndDecision(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patient = await request.post(`${api}/api/v1/patients`, {
    headers: headers(`r6-patient-${suffix}`, "nurse"),
    data: {
      patient_reference: `R6-SYN-${suffix}`,
      safe_demographic_summary: {},
    },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${api}/api/v1/encounters`, {
    headers: headers(`r6-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Synthetic workflow workspace",
      arrival_at: "2026-07-15T08:00:00Z",
    },
  });
  const clinicalCase = await request.post(`${api}/api/v1/clinical-cases`, {
    headers: headers(`r6-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "Synthetic R6 operational workflow",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  const caseValue = await clinicalCase.json();
  const snapshot = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/clinical-reasoning/snapshots`,
    {
      headers: headers(`r6-snapshot-${suffix}`),
      data: { expected_case_version: caseValue.aggregate_version },
    },
  );
  const snapshotValue = await snapshot.json();
  const assessment = await request.post(
    `${api}/api/v1/clinical-cases/${caseValue.case_id}/clinical-reasoning/assessments`,
    {
      headers: headers(`r6-assessment-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        expected_snapshot_version: 1,
        summary: "Physician assessment requiring repeat ECG operations.",
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
      headers: headers(`r6-decision-${suffix}`),
      data: {
        snapshot_id: snapshotValue.snapshot_id,
        assessment_id: assessmentValue.assessment_id,
        expected_snapshot_version: 1,
        expected_assessment_version: 1,
        decision_type: "request_repeat_ecg",
        rationale: "Physician requested a repeat ECG review.",
        uncertainty:
          "This request is not a diagnosis or treatment instruction.",
        evidence_references: ["clinical_case:v1"],
      },
    },
  );
  expect(decision.status(), await decision.text()).toBe(201);
  return { caseId: caseValue.case_id as string };
}

test("R6 standard task lifecycle persists through reload", async ({
  page,
  request,
}) => {
  const { caseId } = await createCaseAndDecision(request);
  await page.goto(`/cases/${caseId}/workflow`);
  await expect(
    page.getByRole("heading", { name: "Active tasks" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create operational task" }).click();
  const generation = page.getByRole("dialog", {
    name: "Create operational task",
  });
  await generation.getByLabel("Priority").selectOption("urgent");
  await generation
    .getByRole("button", { name: "Confirm task creation" })
    .click();
  await expect(page.getByRole("heading", { name: "Repeat ECG" })).toBeVisible();

  await page.getByRole("button", { name: "Assign" }).click();
  const assignDialog = page.getByRole("dialog", { name: "Assign task" });
  const accessibility = await new AxeBuilder({ page })
    .include("main")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await assignDialog.getByRole("button", { name: "Confirm assign" }).click();

  for (const action of ["Acknowledge", "Start"]) {
    await page.getByRole("button", { name: action }).click();
    await page
      .getByRole("dialog", { name: `${action} task` })
      .getByRole("button", { name: `Confirm ${action.toLowerCase()}` })
      .click();
  }
  await page.getByRole("button", { name: "Complete" }).click();
  const completeDialog = page.getByRole("dialog", { name: "Complete task" });
  await completeDialog
    .getByLabel("Required reason")
    .fill("Repeat ECG operational work documented as complete.");
  await completeDialog
    .getByRole("button", { name: "Confirm complete" })
    .click();
  await expect(
    page.getByText("Repeat ECG operational work documented as complete."),
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByText("Repeat ECG operational work documented as complete."),
  ).toBeVisible();
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
});

test("R6 overdue task raises an accessible acknowledgement alert", async ({
  page,
  request,
}) => {
  const { caseId } = await createCaseAndDecision(request);
  await page.goto(`/cases/${caseId}/workflow`);

  await page.getByRole("button", { name: "Create operational task" }).click();
  const generation = page.getByRole("dialog", {
    name: "Create operational task",
  });
  await generation.getByLabel("Due time (optional)").fill("2020-01-01T00:00");
  await generation
    .getByRole("button", { name: "Confirm task creation" })
    .click();

  await page.getByRole("button", { name: "Evaluate due times" }).click();
  await expect(page.getByText("Task Overdue", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Acknowledge" }).click();
  const alertDialog = page.getByRole("dialog", {
    name: "Acknowledge alert",
  });
  await expect(alertDialog).toBeVisible();

  const accessibility = await new AxeBuilder({ page })
    .include("main")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await alertDialog
    .getByRole("button", { name: "Confirm acknowledge" })
    .click();
  await expect(page.getByRole("button", { name: "Resolve" })).toBeVisible();
});
