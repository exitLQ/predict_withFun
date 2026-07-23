const { test, expect } = require("@playwright/test");
const { installApiMocks } = require("./api-mocks");

test("fits a phone viewport and preserves touch-sized controls", async ({ page }) => {
  await installApiMocks(page);
  await page.goto("/");
  await expect(page.locator("#categorySelect")).toBeEnabled();
  await page.locator("#categorySelect").selectOption("politics");
  await page.getByRole("button", { name: /Show markets/ }).click();
  await expect(page.locator(".market-card")).toHaveCount(2);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  for (const control of await page.locator(".market-card button, .market-card a").all()) {
    const box = await control.boundingBox();
    expect(box, "interactive market control should have a layout box").not.toBeNull();
    expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(44);
  }
});
