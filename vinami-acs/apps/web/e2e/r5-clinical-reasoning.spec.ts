import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";

const api = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r5",
  };
}

async function createCase(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patient = await request.post(`${api}/api/v1/patients`, {
    headers: headers(`r5-patient-${suffix}`, "nurse"),
    data: {
      patient_reference: `R5-SYN-${suffix}`,
      safe_demographic_summary: {},
    },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${api}/api/v1/encounters`, {
    headers: headers(`r5-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Synthetic physician workspace",
      arrival_at: "2026-07-15T08:00:00Z",
    },
  });
  expect(encounter.status(), await encounter.text()).toBe(201);
  const clinicalCase = await request.post(`${api}/api/v1/clinical-cases`, {
    headers: headers(`r5-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "Synthetic R5 clinical evidence workspace",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  return (await clinicalCase.json()) as { case_id: string };
}

test("R5 scenario A persists physician-authored assessment and decision", async ({
  page,
  request,
}) => {
  const clinicalCase = await createCase(request);
  await page.goto(`/cases/${clinicalCase.case_id}/clinical-reasoning`);
  await expect(
    page.getByRole("heading", { name: "Clinical evidence synthesis" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create current snapshot" }).click();
  await expect(page.getByText("Missing: troponin")).toBeVisible();
  await page
    .getByRole("checkbox", { name: /Supporting.*clinical_case/ })
    .check();

  const assessment = page
    .getByRole("heading", {
      name: "Physician assessment",
    })
    .locator("..");
  await assessment
    .getByLabel("Assessment summary")
    .fill("Physician-authored synthesis for continued evidence collection.");
  await assessment
    .getByLabel("Uncertainty")
    .fill("ECG and serial troponin evidence remain unavailable.");
  await assessment
    .getByRole("button", { name: "Record physician assessment" })
    .click();
  await expect(
    page.getByText(
      "Physician-authored synthesis for continued evidence collection.",
    ),
  ).toBeVisible();

  const decision = page
    .getByRole("heading", { name: "Physician decision" })
    .locator("..");
  await decision
    .getByLabel("Documented plan")
    .selectOption("continue_observation");
  await decision
    .getByLabel("Rationale")
    .fill(
      "Continue documented observation while additional evidence is obtained.",
    );
  await decision
    .getByLabel("Uncertainty")
    .fill(
      "The current evidence snapshot contains documented missing evidence.",
    );
  await decision.getByRole("button", { name: "Review and confirm" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Confirm physician decision",
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Record physician decision" })
    .click();
  await expect(
    page.getByText(
      "Continue documented observation while additional evidence is obtained.",
    ),
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByText(
      "Continue documented observation while additional evidence is obtained.",
    ),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});
