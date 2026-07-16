import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import path from "node:path";

const apiBase = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";
const screenshots = path.resolve(process.cwd(), "docs/frontend/screenshots");

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r3-completion",
  };
}

async function createCase(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patient = await request.post(`${apiBase}/api/v1/patients`, {
    headers: headers(`r3c-patient-${suffix}`, "nurse"),
    data: {
      patient_reference: `R3C-${suffix}`,
      safe_demographic_summary: {
        age_band: "45-64",
        sex_at_birth: "synthetic",
      },
    },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${apiBase}/api/v1/encounters`, {
    headers: headers(`r3c-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Synthetic ECG Integration Laboratory",
      arrival_at: new Date().toISOString(),
    },
  });
  expect(encounter.status(), await encounter.text()).toBe(201);
  const clinicalCase = await request.post(`${apiBase}/api/v1/clinical-cases`, {
    headers: headers(`r3c-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "R3 completion deterministic scenario",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  return (await clinicalCase.json()) as { case_id: string };
}

async function assertAccessible(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
}

function canonicalXML() {
  const leads = [
    "I",
    "II",
    "III",
    "aVR",
    "aVL",
    "aVF",
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
    "V6",
  ];
  const samples = Array.from({ length: 200 }, (_, index) =>
    Math.round(200 * Math.sin(index / 12)),
  ).join(" ");
  return `<ECGWaveform xmlns="urn:vinami:ecg:canonical:1" device="Playwright fixture" calibration="10 mm/mV"><SamplingRate>100</SamplingRate><AmplitudeUnit>uV</AmplitudeUnit>${leads.map((lead) => `<Lead name="${lead}">${samples}</Lead>`).join("")}</ECGWaveform>`;
}

test("Scenario A - hospital DICOM, canonical XML and PDF-only ingestion", async ({
  page,
  request,
}, testInfo) => {
  const value = await createCase(request);
  await page.goto(`/cases/${value.case_id}/ecg`);
  await expect(
    page.getByRole("heading", { name: "Source and integration" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Import mock DICOM" }).click();
  await expect(
    page.getByText("Mock hospital DICOM request persisted."),
  ).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("Twelve-lead ECG waveform")).toBeVisible();
  await page.screenshot({
    path: path.join(
      screenshots,
      `r3-completion-dicom-${testInfo.project.name}.png`,
    ),
    fullPage: true,
  });

  const input = page.getByLabel("DICOM XML or PDF ECG file");
  await input.setInputFiles({
    name: "canonical.xml",
    mimeType: "application/xml",
    buffer: Buffer.from(canonicalXML()),
  });
  await page.getByRole("button", { name: "Import selected file" }).click();
  await expect(
    page.getByText(/vendor xml stored with provenance/i),
  ).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByText(/urn:vinami:ecg:canonical:1/i).first(),
  ).toBeVisible();
  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.join(screenshots, "r3-completion-xml-desktop.png"),
      fullPage: true,
    });
  }

  await input.setInputFiles({
    name: "source.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF"),
  });
  await page.getByRole("button", { name: "Import selected file" }).click();
  await expect(page.getByText(/Source document only/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByTitle("PDF ECG source document preview"),
  ).toBeVisible();
  await expect(
    page.getByText(/automated waveform analysis is unavailable/i).first(),
  ).toBeVisible();
  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.join(screenshots, "r3-completion-pdf-only-desktop.png"),
      fullPage: true,
    });
    await page.getByLabel("Baseline study").selectOption({ index: 1 });
    await page.getByLabel("Current study").selectOption({ index: 3 });
    await page
      .getByRole("button", { name: "Compare technical signals" })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: /waveform unavailable/i }),
    ).toBeVisible({ timeout: 20_000 });
    await page.screenshot({
      path: path.join(screenshots, "r3-completion-non-comparable-desktop.png"),
      fullPage: true,
    });
  }
  await assertAccessible(page);
});

test("Scenario B - persisted connector timeout and safe retry", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name === "tablet",
    "Desktop-only R3 completion scenario",
  );
  const value = await createCase(request);
  await page.goto(`/cases/${value.case_id}/ecg`);
  await page.getByRole("button", { name: "Exercise timeout path" }).click();
  await expect(page.getByText(/requires a safe retry/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.screenshot({
    path: path.join(screenshots, "r3-completion-ingestion-failure-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Safe retry" }).click();
  await expect(page.getByText(/without creating a duplicate job/i)).toBeVisible(
    { timeout: 20_000 },
  );
  await expect(page.getByText(/retries 1/i)).toBeVisible();
  await assertAccessible(page);
});

test("Scenario C - Dynamic ECG comparison and physician review", async ({
  page,
  request,
}, testInfo) => {
  const value = await createCase(request);
  await page.goto(`/cases/${value.case_id}/ecg`);
  await page.getByRole("button", { name: "Import mock DICOM" }).click();
  await expect(page.getByText(/persisted/i).first()).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run research-use analysis" }).click();
  await expect(page.getByText(/analysis completed/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Add serial ECG" }).click();
  await expect(page.getByText(/ingested and quality assessed/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Run research-use analysis" }).click();
  await expect(page.getByText(/analysis completed/i)).toBeVisible({
    timeout: 20_000,
  });

  const baseline = page.getByLabel("Baseline study");
  const current = page.getByLabel("Current study");
  await baseline.selectOption({ index: 1 });
  await current.selectOption({ index: 2 });
  await page.getByRole("button", { name: "Compare technical signals" }).click();
  await expect(page.getByText(/comparison persisted/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText(/Lead-by-lead non-diagnostic technical metrics/i),
  ).toBeVisible();
  await expect(
    page.getByText(/Compatible model-score evolution/i),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(
      screenshots,
      `r3-completion-dynamic-${testInfo.project.name}.png`,
    ),
    fullPage: true,
  });

  await page
    .getByLabel("Physician comparison review")
    .fill(
      "Synthetic technical comparison reviewed; clinical correlation remains required.",
    );
  if (testInfo.project.name === "desktop") {
    await page.screenshot({
      path: path.join(screenshots, "r3-completion-dynamic-review-desktop.png"),
      fullPage: true,
    });
  }
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Record physician review" })
    .last()
    .click();
  await expect(page.getByText(/recorded immutably/i)).toBeVisible({
    timeout: 20_000,
  });
  const workspace = await request.get(
    `${apiBase}/api/v1/clinical-cases/${value.case_id}/ecg-workspace`,
    { headers: headers(`r3c-workspace-${crypto.randomUUID()}`) },
  );
  expect(workspace.status(), await workspace.text()).toBe(200);
  const comparisonId = (await workspace.json()).comparisons[0]
    .comparison_id as string;
  const staleReview = await request.post(
    `${apiBase}/api/v1/ecg-comparisons/${comparisonId}/physician-reviews`,
    {
      headers: headers(`r3c-stale-review-${crypto.randomUUID()}`),
      data: {
        review_status: "reviewed",
        interpretation:
          "Synthetic stale review must not overwrite the current review.",
        occurred_at: new Date().toISOString(),
        expected_version: 0,
      },
    },
  );
  expect(staleReview.status()).toBe(409);
  await assertAccessible(page);
});

test("Scenario D - repeat ECG lifecycle and stale review rejection", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    testInfo.project.name === "tablet",
    "Desktop-only R3 completion scenario",
  );
  const value = await createCase(request);
  await page.goto(`/cases/${value.case_id}/ecg`);
  await page
    .getByRole("button", { name: "Load synthetic 12-lead ECG" })
    .click();
  await expect(page.getByText(/ingested and quality assessed/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Schedule +30 min" }).click();
  await expect(page.getByText(/reminder scheduled/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.screenshot({
    path: path.join(screenshots, "r3-completion-repeat-reminder-desktop.png"),
    fullPage: true,
  });
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Acknowledge" }).click();
  await expect(page.getByText(/acknowledge action recorded/i)).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Add serial ECG" }).click();
  await expect(page.getByText(/ingested and quality assessed/i)).toBeVisible({
    timeout: 20_000,
  });
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Complete with subsequent ECG" })
    .click();
  await expect(page.getByText(/complete action recorded/i)).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByText("completed", { exact: true }).first(),
  ).toBeVisible();
  await assertAccessible(page);
});
