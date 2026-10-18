import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 860 } } },
  ],
  webServer: [
    {
      command: "cd ../services/api && rm -f e2e.db e2e.db-wal e2e.db-shm && DATABASE_URL=sqlite:///./e2e.db .venv/bin/uvicorn helm.main:app --port 8000",
      url: "http://localhost:8000/health", reuseExistingServer: !process.env.CI, timeout: 90_000,
    },
    {
      command: "cd ../apps/web && pnpm exec next start -p 3000",
      url: "http://localhost:3000", reuseExistingServer: !process.env.CI, timeout: 90_000,
    },
  ],
});
