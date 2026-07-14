import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const screenshots = path.resolve(process.cwd(), "docs/frontend/screenshots");

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
    .analyze();
  expect(
    results.violations,
    results.violations
      .map((violation) => `${violation.id}: ${violation.help}`)
      .join("\n"),
  ).toEqual([]);
}

test.describe.serial("R1 clinical lifecycle frontend", () => {
  test("Command Center filters, selects and opens a real PostgreSQL-backed case", async ({
    page,
  }, testInfo) => {
    await page.goto("/command-center");
    await expect(
      page.getByRole("heading", { name: "Active Clinical Case Queue" }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Active suspected ACS cases" }),
    ).toBeVisible();
    await page.getByLabel("Priority").selectOption("critical");
    await expect(page).toHaveURL(/priority=critical/);
    await expect(page.getByText("R1-SYN-001")).toBeVisible();
    await expect(page.getByText("Synthetic Physician")).toBeVisible();
    await expect(
      page.getByText("Development identity", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: /actor|role/i }),
    ).toHaveCount(0);
    await page.screenshot({
      path: path.join(screenshots, "command-center-1440.png"),
      fullPage: true,
    });

    await expect(page.getByText("R1-SYN-001")).toBeVisible();
    await expect(page.getByText("R1-SYN-002")).toHaveCount(0);
    await page.getByRole("row", { name: /R1-SYN-001/ }).press("Enter");
    await expect(
      page.getByRole("heading", { name: "Selected case" }),
    ).toBeVisible();
    await expect(
      page.getByText("CASE-0390099F", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Recent lifecycle events")).toBeVisible();
    await page.screenshot({
      path: path.join(screenshots, "selected-case.png"),
      fullPage: true,
    });
    await expectAccessible(page);

    await Promise.all([
      page.waitForURL(/\/cases\/[0-9a-f-]+$/),
      page.getByRole("link", { name: "Open case workspace" }).click(),
    ]);
    await expect(
      page.getByRole("heading", { name: "R1-SYN-001" }),
    ).toBeVisible();
    await expect(page.getByText("Capabilities not yet enabled:")).toBeVisible();
    await page.screenshot({
      path: path.join(screenshots, "case-workspace.png"),
      fullPage: true,
    });
    await expect(page).toHaveScreenshot("case-workspace.png", {
      fullPage: true,
    });
    await expectAccessible(page);
    await testInfo.attach("case-workspace", {
      path: path.join(screenshots, "case-workspace.png"),
      contentType: "image/png",
    });
  });

  test("Timeline and immutable Audit render real persisted projections", async ({
    page,
  }) => {
    await page.goto("/command-center?priority=critical");
    await page.getByRole("row", { name: /R1-SYN-001/ }).click();
    await Promise.all([
      page.waitForURL(/\/cases\/[0-9a-f-]+$/),
      page.getByRole("link", { name: "Open case workspace" }).click(),
    ]);
    await Promise.all([
      page.waitForURL(/\/timeline$/),
      page
        .getByLabel("Case workspace sections")
        .getByRole("link", { name: "Timeline" })
        .click(),
    ]);
    await expect(
      page.getByRole("heading", { name: "Lifecycle Timeline" }),
    ).toBeVisible();
    await expect(page.getByText("Suspected ACS case opened")).toBeVisible();
    await page.screenshot({
      path: path.join(screenshots, "timeline.png"),
      fullPage: true,
    });
    await expectAccessible(page);

    const auditLink = page
      .getByLabel("Case workspace sections")
      .getByRole("link", { name: "Audit" });
    await expect(auditLink).toHaveAttribute("href", /\/audit$/);
    await Promise.all([page.waitForURL(/\/audit$/), auditLink.click()]);
    await expect(
      page.getByRole("heading", { name: "Immutable Audit" }),
    ).toBeVisible();
    await expect(
      page.getByRole("table", { name: "Immutable case audit history" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /edit|delete/i }),
    ).toHaveCount(0);
    await page.screenshot({
      path: path.join(screenshots, "audit.png"),
      fullPage: true,
    });
    await expectAccessible(page);
  });

  test("System Health remains separate from clinical workflow", async ({
    page,
  }) => {
    await page.goto("/system-health");
    await expect(
      page.getByRole("heading", { name: "System Health" }),
    ).toBeVisible();
    await expect(page.getByText("FastAPI liveness")).toBeVisible();
    await expect(page.getByText("Worker", { exact: true })).toBeVisible();
    await expect(page.getByText("Not exposed", { exact: true })).toBeVisible();
    await page.screenshot({
      path: path.join(screenshots, "system-health.png"),
      fullPage: true,
    });
    await expectAccessible(page);
  });

  test("Safety language excludes autonomous clinical claims", async ({
    page,
  }) => {
    await page.goto("/command-center");
    const text = (await page.locator("body").innerText()).toLowerCase();
    for (const prohibited of [
      "ami ruled out",
      "patient diagnosed by ai",
      "cath lab activated by ai",
      "clinically validated",
      "production ready",
    ]) {
      expect(text).not.toContain(prohibited);
    }
  });
});

test("responsive Command Center screenshots", async ({ page }, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "Captured once with the desktop browser engine",
  );
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/command-center");
  await page.screenshot({
    path: path.join(screenshots, "command-center-1920.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({
    path: path.join(screenshots, "command-center-1280.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({
    path: path.join(screenshots, "command-center-tablet.png"),
    fullPage: true,
  });
});
