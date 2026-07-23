const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const { installApiMocks } = require("./api-mocks");

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
  await page.goto("/");
  await expect(page.locator("#categorySelect")).toBeEnabled();
});

async function expectNoWcagViolations(page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

test("has no detectable WCAG A or AA violations", async ({ page }) => {
  await expectNoWcagViolations(page);
  await page.locator("#categorySelect").selectOption("politics");
  await page.getByRole("button", { name: /Show markets/ }).click();
  await expect(page.locator(".market-card")).toHaveCount(2);
  await expectNoWcagViolations(page);
});

test("supports skip navigation and account keyboard controls", async ({ page }) => {
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#mainContent")).toBeFocused();

  const account = page.locator("#toggleAccount");
  await account.focus();
  await page.keyboard.press("Enter");
  await expect(account).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#accountEmail")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#accountPanel")).toBeHidden();
  await expect(account).toBeFocused();
});
