import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext } from "@playwright/test";
import path from "node:path";

const apiBase = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";
const screenshots = path.resolve(process.cwd(), "docs/frontend/screenshots");

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r3",
  };
}

async function createCase(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patient = await request.post(`${apiBase}/api/v1/patients`, {
    headers: headers(`r3-patient-${suffix}`, "nurse"),
    data: {
      patient_reference: `R3-E2E-${suffix}`,
      safe_demographic_summary: {
        age_band: "45-64",
        sex_at_birth: "synthetic",
      },
    },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${apiBase}/api/v1/encounters`, {
    headers: headers(`r3-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Synthetic ECG Laboratory",
      arrival_at: new Date().toISOString(),
    },
  });
  expect(encounter.status(), await encounter.text()).toBe(201);
  const clinicalCase = await request.post(`${apiBase}/api/v1/clinical-cases`, {
    headers: headers(`r3-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "R3 Playwright ECG vertical slice",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  return (await clinicalCase.json()) as { case_id: string };
}

test("R3 ECG golden path is clear, auditable, and clinically bounded", async ({
  page,
  request,
}) => {
  const clinicalCase = await createCase(request);
  await page.goto(`/cases/${clinicalCase.case_id}`);

  await expect(
    page.getByRole("heading", { name: "ECG review workspace" }),
  ).toBeVisible();
  await expect(
    page.getByText(/ECG and model scores cannot rule out AMI/),
  ).toBeVisible();
  await expect(
    page.getByText("No ECG study recorded for this case"),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Load synthetic 12-lead ECG" })
    .click();
  await expect(page.getByText(/ingested and quality assessed/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByLabel("Twelve-lead ECG waveform")).toBeVisible();
  await expect(
    page.getByText("acceptable", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshots, "r3-ecg-waveform-quality-desktop.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "Run research-use analysis" }).click();
  await expect(page.getByText(/analysis completed/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("MI-related ECG pattern")).toBeVisible();
  await expect(page.getByText(/scores do not need to sum to 1/i)).toBeVisible();
  await expect(page.getByText(/not clinical probabilities/i)).toBeVisible();
  await page.screenshot({
    path: path.join(screenshots, "r3-ecg-multilabel-ranking-desktop.png"),
    fullPage: true,
  });

  await page
    .getByLabel("Structured review summary")
    .fill(
      "Synthetic physician review; correlate with symptoms and serial troponin.",
    );
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Record physician review" }).click();
  await expect(
    page.getByText(/Physician review recorded with model provenance/i),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText(/Synthetic physician review/)).toBeVisible();

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
