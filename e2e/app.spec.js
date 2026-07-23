const { test, expect } = require("@playwright/test");

const markets = [
  {
    slug: "senate-control",
    title: "Will one party control the Senate?",
    description: "Senate control market",
    volume: 250000,
    liquidity: 45000,
    outcomes: [
      { title: "Yes", price: 0.62, probability: 0.62 },
      { title: "No", price: 0.38, probability: 0.38 },
    ],
    category: "Politics",
    active: true,
    url: "https://polymarket.com/event/senate-control",
    token_id: "token-1",
  },
  {
    slug: "governor-race",
    title: "Will the incumbent win the governor race?",
    description: "Governor race market",
    volume: 125000,
    liquidity: 30000,
    outcomes: [
      { title: "Yes", price: 0.48, probability: 0.48 },
      { title: "No", price: 0.52, probability: 0.52 },
    ],
    category: "Politics",
    active: true,
    url: "https://polymarket.com/event/governor-race",
    token_id: "token-2",
  },
];

const analysis = {
  category: "Politics",
  summary: "Primary polling and institutional evidence suggest a close race.",
  overall_insights: "Uncertainty remains elevated.",
  markets: [
    {
      market_slug: "senate-control",
      market_title: "Will one party control the Senate?",
      market_probability: 0.62,
      fair_probability: 0.67,
      assessment: "undervalued",
      risks: ["Polling error"],
      reasoning: "Recent primary evidence supports a modestly higher estimate.",
    },
  ],
  sources: [
    {
      title: "Election authority",
      url: "https://example.gov/elections",
      domain: "example.gov",
      category: "government",
      quality: "high",
      quality_score: 0.9,
      quality_reason: "Primary government source",
    },
  ],
  demo: false,
  cached: false,
  research_provider: "openai",
  requested_provider: "openai",
  fallback_used: false,
  usage: {
    input_tokens: 100,
    output_tokens: 50,
    search_calls: 1,
    estimated_cost_usd: 0.01,
  },
};

const savedItem = {
  id: "saved-analysis",
  created_at: "2026-07-23T10:00:00Z",
  category: "Politics",
  provider: "openai",
  requested_provider: "openai",
  market_count: 1,
  estimated_cost_usd: 0.01,
  resolved_outcome: null,
  brier_score: null,
};

async function installApiMocks(page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body, status = 200, headers = {}) =>
      route.fulfill({
        status,
        contentType: "application/json",
        headers,
        body: JSON.stringify(body),
      });

    if (path === "/api/health") {
      return json({
        status: "ok",
        openai_configured: true,
        grok_configured: false,
        claude_configured: false,
        redis_configured: false,
        background_queue: "local",
        demo_mode: false,
      });
    }
    if (path === "/api/auth/me") return json({ detail: "Authentication required." }, 401);
    if (path === "/api/auth/login" && request.method() === "POST") {
      return json({
        id: "user-1",
        email: "person@example.com",
        role: "user",
        created_at: "2026-07-23T10:00:00Z",
      });
    }
    if (path === "/api/categories") {
      return json([{ id: "politics", name: "Politics", description: null }]);
    }
    if (path === "/api/markets/politics") return json(markets);
    if (path === "/api/analyze" && request.method() === "POST") return json(analysis);
    if (path === "/api/analyses/saved-analysis") return json(analysis);
    if (path === "/api/analyses") return json([savedItem]);
    if (path === "/api/accuracy") return json([]);
    if (path === "/api/accuracy/calibration") return json([]);
    return json({ detail: `Unhandled mock route: ${request.method()} ${path}` }, 501);
  });
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
  await page.goto("/");
  await expect(page.locator("#categorySelect")).toBeEnabled();
});

test("loads, filters, and saves markets", async ({ page }) => {
  await page.locator("#categorySelect").selectOption("politics");
  await page.getByRole("button", { name: /Show markets/ }).click();

  await expect(page.locator(".market-card")).toHaveCount(2);
  await expect(page.locator("#marketsHeading")).toHaveText("Politics");

  await page.locator("#marketSearch").fill("Senate");
  await expect(page.locator(".market-card")).toHaveCount(1);
  await expect(page.locator(".market-card h3")).toContainText("Senate");

  await page.locator("#marketSearch").fill("");
  await page.locator(".market-card").first().getByRole("button", { name: /Watch/ }).click();
  await page.locator("#marketView").selectOption("watchlist");
  await expect(page.locator(".market-card")).toHaveCount(1);
  await expect(page.locator(".watch-button")).toContainText("Saved");
});

test("renders a mocked provider analysis with sources", async ({ page }) => {
  await page.locator("#categorySelect").selectOption("politics");
  await page.getByRole("button", { name: /Show markets/ }).click();
  await page.getByRole("button", { name: /Analyze with AI/ }).click();

  await expect(page.locator("#analysisSection")).toBeVisible();
  await expect(page.locator(".analysis-summary")).toContainText("Primary polling");
  await expect(page.locator(".analysis-card")).toContainText("67.0%");
  await expect(page.locator(".sources a")).toHaveText("1. Election authority");
});

test("signs in and restores a saved analysis", async ({ page }) => {
  await page.getByRole("button", { name: "Account" }).click();
  await page.locator("#accountEmail").fill("person@example.com");
  await page.locator("#accountPassword").fill("long-test-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.locator("#accountSummary")).toContainText("person@example.com");
  await page.locator(".saved-analysis-row").getByRole("button", { name: "Open result" }).click();
  await expect(page.locator(".saved-result-banner")).toContainText("Saved analysis");
  await expect(page.locator(".analysis-summary")).toContainText("Primary polling");
});
