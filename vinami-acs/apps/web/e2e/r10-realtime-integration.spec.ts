import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const api = process.env.VINAMI_API_BASE_URL ?? "http://127.0.0.1:8000";
const clinicalTime = "2026-07-16T09:00:00Z";

function headers(key: string, identity = "physician") {
  return {
    "Idempotency-Key": key,
    "X-Correlation-ID": crypto.randomUUID(),
    "X-Development-Identity": identity,
    "X-Request-Source": "playwright-r10-release",
  };
}

async function createCase(request: APIRequestContext) {
  const suffix = `${Date.now()}-${crypto.randomUUID()}`;
  const patientReference = `R10-SYN-${suffix}`;
  const patient = await request.post(`${api}/api/v1/patients`, {
    headers: headers(`r10-patient-${suffix}`, "nurse"),
    data: { patient_reference: patientReference, safe_demographic_summary: {} },
  });
  expect(patient.status(), await patient.text()).toBe(201);
  const encounter = await request.post(`${api}/api/v1/encounters`, {
    headers: headers(`r10-encounter-${suffix}`, "nurse"),
    data: {
      patient_id: (await patient.json()).patient_id,
      location: "Emergency Department",
      arrival_at: clinicalTime,
    },
  });
  expect(encounter.status(), await encounter.text()).toBe(201);
  const clinicalCase = await request.post(`${api}/api/v1/clinical-cases`, {
    headers: headers(`r10-case-${suffix}`),
    data: {
      encounter_id: (await encounter.json()).encounter_id,
      opening_reason: "Synthetic R10 real-time integration validation",
      priority: "urgent",
    },
  });
  expect(clinicalCase.status(), await clinicalCase.text()).toBe(201);
  const caseValue = await clinicalCase.json();
  return {
    caseId: caseValue.case_id as string,
    caseVersion: caseValue.aggregate_version as number,
    patientReference,
    suffix,
  };
}

async function importLabResult(
  request: APIRequestContext,
  value: Awaited<ReturnType<typeof createCase>>,
  externalId: string,
  troponinValue = "18.7",
) {
  const response = await request.post(
    `${api}/api/v1/integration/simulated/laboratory-results`,
    {
      headers: headers(`r10-lab-${externalId}`),
      data: {
        external_message_id: externalId,
        source_system: "simulated-lis-r10",
        schema_version: "vinami-hl7-lab-result.v1",
        clinical_case_id: value.caseId,
        assay_code: "DEMO-HS-CTNI-01",
        analyte: "cardiac_troponin_i",
        value: troponinValue,
        unit: "ng/L",
        specimen_type: "plasma",
        specimen_collected_at: clinicalTime,
        resulted_at: "2026-07-16T09:02:00Z",
        result_status: "final",
        source_result_id: externalId,
        expected_case_version: value.caseVersion,
      },
    },
  );
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

async function importInvalidLabResult(
  request: APIRequestContext,
  value: Awaited<ReturnType<typeof createCase>>,
  externalId: string,
) {
  const response = await request.post(
    `${api}/api/v1/integration/simulated/laboratory-results`,
    {
      headers: headers(`r10-invalid-${externalId}`),
      data: {
        external_message_id: externalId,
        source_system: "simulated-lis-r10",
        schema_version: "vinami-hl7-lab-result.v1",
        clinical_case_id: value.caseId,
        assay_code: "DEMO-HS-CTNI-01",
        analyte: "cardiac_troponin_i",
        value: "22.3",
        unit: "mg/dL",
        specimen_type: "plasma",
        specimen_collected_at: clinicalTime,
        resulted_at: "2026-07-16T09:03:00Z",
        result_status: "final",
        source_result_id: externalId,
        expected_case_version: value.caseVersion,
      },
    },
  );
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

async function expectRealtimeConnected(page: Page) {
  await expect(page.getByText("Real-time updates")).toBeVisible();
  await expect(page.getByText("connected", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
}

test("R10 scenario A - real-time lab import refreshes authoritative case data without duplicates", async ({
  browser,
  request,
}) => {
  const value = await createCase(request);
  const context = await browser.newContext();
  const commandCenter = await context.newPage();
  const workspace = await context.newPage();

  await commandCenter.goto("/command-center");
  await workspace.goto(`/cases/${value.caseId}`);
  await expectRealtimeConnected(commandCenter);
  await expectRealtimeConnected(workspace);
  await expect(
    workspace.getByText("No effective troponin result"),
  ).toBeVisible();

  const externalId = `R10-LAB-${value.suffix}`;
  const message = await importLabResult(request, value, externalId);
  expect(message.status).toBe("processed");

  await expect(
    workspace.getByText("New integration update received", { exact: false }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(workspace.getByText(/18\.7[0-9]* ng\/L/)).toBeVisible({
    timeout: 15_000,
  });

  const duplicate = await importLabResult(request, value, externalId);
  expect(duplicate.message_id).toBe(message.message_id);
  await workspace.reload();
  await expect(workspace.getByText(/18\.7[0-9]* ng\/L/)).toHaveCount(1);

  await commandCenter
    .getByRole("row", { name: new RegExp(value.patientReference) })
    .click();
  await expect(
    commandCenter.getByRole("complementary", {
      name: "Selected case quick view",
    }),
  ).toBeVisible();

  const accessibility = await new AxeBuilder({ page: workspace })
    .include("main")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);

  await context.close();
});

test("R10 scenario B - reconnect state and failed integration message remain visible", async ({
  page,
  request,
}) => {
  const value = await createCase(request);
  await page.route("**/api/realtime/events**", (route) => route.abort());
  await page.goto(`/cases/${value.caseId}`);
  await expect(page.getByText("Real-time updates")).toBeVisible();
  await expect(
    page.getByText(/disconnected|reconnecting/, { exact: false }),
  ).toBeVisible({ timeout: 15_000 });

  await page.unroute("**/api/realtime/events**");
  await page.reload();
  await expectRealtimeConnected(page);

  const invalid = await importInvalidLabResult(
    request,
    value,
    `R10-BAD-${value.suffix}`,
  );
  expect(["failed", "dead_letter"]).toContain(invalid.status);

  await expect(
    page.getByText("New integration update received", { exact: false }),
  ).toBeVisible({ timeout: 15_000 });
  const failedMessage = page
    .locator(".vm-integration-errors article")
    .filter({ hasText: "simulated-lis-r10 - lab_result" })
    .first();
  await expect(failedMessage.getByText("failed", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(failedMessage).toContainText("simulated-lis-r10 - lab_result");

  const accessibility = await new AxeBuilder({ page })
    .include(".vm-realtime")
    .include(".vm-integration-panel")
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});
