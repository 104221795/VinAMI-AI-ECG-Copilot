import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const api = "http://127.0.0.1:8000";

test("R4.1 - Troponin workspace has no blocking axe violations", async ({
  page,
  request,
}) => {
  const response = await request.get(
    `${api}/api/v1/clinical-cases?page_size=1`,
    {
      headers: { "X-Development-Identity": "physician" },
    },
  );
  expect(response.ok()).toBeTruthy();
  const clinicalCase = (await response.json()).items[0] as { case_id: string };
  await page.goto(`/cases/${clinicalCase.case_id}/troponin`);
  await expect(
    page.getByRole("heading", { name: "Serial troponin" }),
  ).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});
