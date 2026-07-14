import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const storybook = process.env.STORYBOOK_BASE_URL;
const screenshots = path.resolve(process.cwd(), "docs/frontend/screenshots");

test.describe("design-system operational states", () => {
  test.skip(
    !storybook,
    "STORYBOOK_BASE_URL is required for state visual validation",
  );

  for (const [name, story] of [
    ["loading-state.png", "loading"],
    ["error-state.png", "error"],
    ["offline-state.png", "offline"],
    ["empty-state.png", "empty"],
  ] as const) {
    test(name, async ({ page }, testInfo) => {
      test.skip(
        testInfo.project.name !== "desktop",
        "State captures run once on desktop",
      );
      await page.goto(
        `${storybook}/iframe.html?id=clinical-foundation-design-system--${story}&viewMode=story`,
      );
      await page.locator("#storybook-root").waitFor();
      await page.screenshot({
        path: path.join(screenshots, name),
        fullPage: true,
      });
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(results.violations).toEqual([]);
    });
  }
});
