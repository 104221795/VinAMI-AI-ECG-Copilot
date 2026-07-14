import { expect, test } from "@playwright/test";

function problem(status: number) {
  return {
    type: "urn:controlled-test",
    title: "Controlled failure",
    status,
    detail: "Controlled browser contract failure",
    instance: "/controlled",
    correlation_id: "7fc88d15-f71f-4baf-b65a-741d05058f08",
  };
}

test.describe("controlled frontend failure behavior", () => {
  test("distinguishes missing session, permission denial and server failure", async ({
    page,
  }) => {
    for (const [status, priority, heading] of [
      [401, "critical", "Session unavailable"],
      [403, "urgent", "Permission required"],
      [500, "routine", "Clinical service unavailable"],
    ] as const) {
      await page.goto("/command-center");
      await page.route(
        "**/api/backend/api/v1/clinical-cases**",
        async (route) =>
          route.fulfill({
            status,
            contentType: "application/problem+json",
            body: JSON.stringify(problem(status)),
          }),
        { times: 1 },
      );
      await page.getByLabel("Priority").selectOption(priority);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await page.getByText("Technical reference").click();
      await expect(
        page.getByText("Correlation 7fc88d15-f71f-4baf-b65a-741d05058f08"),
      ).toBeVisible();
    }
  });

  test("rejects a malformed API response", async ({ page }) => {
    await page.goto("/command-center");
    await page.route(
      "**/api/backend/api/v1/clinical-cases**",
      async (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ unexpected: true }),
        }),
      { times: 1 },
    );
    await page.getByLabel("Priority").selectOption("critical");
    await expect(
      page.getByRole("heading", { name: "Contract mismatch detected" }),
    ).toBeVisible();
  });

  test("shows an explicit offline state for an unfetched filter", async ({
    page,
    context,
  }) => {
    await page.goto("/command-center");
    await context.setOffline(true);
    await page.getByLabel("Priority").selectOption("critical");
    await expect(page.getByText("Offline", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Connection unavailable" }),
    ).toBeVisible();
    await context.setOffline(false);
  });

  test("shows not-found safely for a missing case", async ({ page }) => {
    await page.goto("/cases/00000000-0000-4000-8000-000000000001", {
      waitUntil: "domcontentloaded",
    });
    await expect(
      page.getByRole("heading", { name: "Record not found" }),
    ).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Traceback");
  });

  test("communicates an empty eventual-consistency projection", async ({
    page,
  }) => {
    await page.goto("/command-center?priority=critical");
    await page.route(
      "**/api/backend/api/v1/clinical-cases/*/timeline",
      async (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        }),
      { times: 1 },
    );
    await page.getByRole("row", { name: /R1-SYN-001/ }).click();
    await expect(
      page.getByText("Lifecycle projection is still processing."),
    ).toBeVisible();
  });
});
