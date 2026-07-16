import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

const identity = "physician";
const api = "http://127.0.0.1:8000";

async function activeCase(request: APIRequestContext) {
  const response = await request.get(
    `${api}/api/v1/clinical-cases?page_size=1`,
    {
      headers: { "X-Development-Identity": identity },
    },
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()).items[0] as {
    case_id: string;
    aggregate_version: number;
  };
}

test("A - serial troponin workspace persists and remains usable at desktop and tablet", async ({
  page,
  request,
}) => {
  const clinicalCase = await activeCase(request);
  await page.goto(`/cases/${clinicalCase.case_id}/troponin`);
  await expect(
    page.getByRole("heading", { name: "Serial troponin" }),
  ).toBeVisible();
  await expect(
    page.getByText("Clinician interpretation required.", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "docs/frontend/screenshots/r4-troponin-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 820, height: 1180 });
  await expect(page.getByRole("table").first()).toBeVisible();
  await page.screenshot({
    path: "docs/frontend/screenshots/r4-troponin-tablet.png",
    fullPage: true,
  });
});

test("B - deterministic mock lifecycle preserves preliminary, final, and amended history", async ({
  page,
  request,
}) => {
  const clinicalCase = await activeCase(request);
  const headers = {
    "X-Development-Identity": identity,
    "X-Correlation-ID": crypto.randomUUID(),
    "Idempotency-Key": crypto.randomUUID(),
    "Content-Type": "application/json",
  };
  const headersFor = () => ({
    ...headers,
    "Idempotency-Key": crypto.randomUUID(),
  });
  const body = (external_reference: string) => ({
    connector_id: "mock-lab-r4",
    external_reference,
    expected_case_version: clinicalCase.aggregate_version,
  });
  for (const reference of ["preliminary", "final", "amended"]) {
    const response = await request.post(
      `${api}/api/v1/clinical-cases/${clinicalCase.case_id}/troponin-imports`,
      { headers: headersFor(), data: body(reference) },
    );
    expect(response.ok()).toBeTruthy();
  }
  const duplicate = await request.post(
    `${api}/api/v1/clinical-cases/${clinicalCase.case_id}/troponin-imports`,
    { headers: headersFor(), data: body("duplicate-amended") },
  );
  expect(duplicate.ok()).toBeTruthy();
  expect((await duplicate.json()).warnings).toContain(
    "Duplicate source delivery reused the existing result.",
  );
  await page.goto(`/cases/${clinicalCase.case_id}/troponin`);
  await expect(page.getByText("Local/mock only.")).toBeVisible();
  await expect(page.getByText("preliminary", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("cell", { name: "amended" }).first(),
  ).toBeVisible();
});

test("C - unsupported unit and stale amendment are rejected without clinical authority language", async ({
  page,
  request,
}) => {
  const clinicalCase = await activeCase(request);
  const workspace = await request.get(
    `${api}/api/v1/clinical-cases/${clinicalCase.case_id}/troponin-workspace`,
    { headers: { "X-Development-Identity": identity } },
  );
  const latest = (await workspace.json()).latest_result as {
    result_id: string;
    record_version: number;
  };
  const bad = await request.post(
    `${api}/api/v1/clinical-cases/${clinicalCase.case_id}/troponin-results`,
    {
      headers: {
        "X-Development-Identity": identity,
        "X-Correlation-ID": crypto.randomUUID(),
        "Idempotency-Key": crypto.randomUUID(),
      },
      data: {
        assay_code: "DEMO-HS-CTNI-01",
        analyte: "cardiac_troponin_i",
        value: "1",
        unit: "mg/dL",
        specimen_type: "plasma",
        specimen_collected_at: new Date().toISOString(),
        resulted_at: new Date().toISOString(),
        result_status: "final",
        quality_flags: [],
        source_system: "r4-test",
        source_result_id: crypto.randomUUID(),
        expected_case_version: clinicalCase.aggregate_version,
      },
    },
  );
  expect(bad.status()).toBe(422);
  expect((await bad.json()).errors).toEqual([
    { field: "unit", code: "unsupported_unit" },
  ]);
  const stale = await request.post(
    `${api}/api/v1/troponin-results/${latest.result_id}/amendments`,
    {
      headers: {
        "X-Development-Identity": identity,
        "X-Correlation-ID": crypto.randomUUID(),
        "Idempotency-Key": crypto.randomUUID(),
      },
      data: {
        value: "2",
        unit: "ng/L",
        result_status: "amended",
        amendment_reason: "Synthetic stale-version test",
        resulted_at: new Date().toISOString(),
        expected_version: latest.record_version + 10,
      },
    },
  );
  expect(stale.status()).toBe(409);
  await page.goto(`/cases/${clinicalCase.case_id}/troponin`);
  const text = (await page.locator("body").innerText()).toLowerCase();
  expect(text).not.toContain("cath lab");
  expect(text).not.toContain("treatment recommendation");
  expect(text).not.toContain("ami-positive");
  expect(text).not.toContain("ami-negative");
});
