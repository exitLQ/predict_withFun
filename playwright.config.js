const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["line"], ["html", { open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
      },
    },
  ],
  webServer: {
    command: "python -m uvicorn app:app --host 127.0.0.1 --port 8765",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
    env: {
      ...process.env,
      ALLOWED_HOSTS: "127.0.0.1",
      AUTH_REQUIRED: "false",
      DATABASE_URL: "sqlite:///./e2e-test.db",
      DEMO_MODE: "true",
      ENVIRONMENT: "development",
      HTTPS_REDIRECT: "false",
    },
  },
});
