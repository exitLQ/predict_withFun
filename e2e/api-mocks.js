const markets = [{
  slug: "senate-control",
  title: "Will one party control the Senate?",
  volume: 250000,
  liquidity: 45000,
  outcomes: [{ title: "Yes", price: 0.62, probability: 0.62 }],
  category: "Politics",
  active: true,
  url: "https://polymarket.com/event/senate-control",
  token_id: "token-1",
}, {
  slug: "governor-race",
  title: "Will the incumbent win the governor race?",
  volume: 125000,
  liquidity: 30000,
  outcomes: [{ title: "No", price: 0.52, probability: 0.52 }],
  category: "Politics",
  active: true,
  url: "https://polymarket.com/event/governor-race",
  token_id: "token-2",
}];

async function installApiMocks(page) {
  await page.route("https://fonts.g**", (route) => route.abort());
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const responses = {
      "/api/health": { status: "ok", openai_configured: true, demo_mode: false },
      "/api/categories": [{ id: "politics", name: "Politics", description: null }],
      "/api/markets/politics": markets,
      "/api/analyses": [],
      "/api/accuracy": [],
      "/api/accuracy/calibration": [],
    };
    const status = path === "/api/auth/me" ? 401 : responses[path] === undefined ? 501 : 200;
    const body = path === "/api/auth/me"
      ? { detail: "Authentication required." }
      : responses[path] ?? { detail: `Unhandled mock route: ${path}` };
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
}

module.exports = { installApiMocks };
