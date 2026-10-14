import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : [
        {
          command: "node scripts/e2e-server.mjs",
          url: "http://127.0.0.1:8001/health/ready",
          timeout: 120000,
          reuseExistingServer: process.env.E2E_REUSE_SERVER === "true",
        },
        {
          command: "npm run dev -- --port 5173 --strictPort",
          env: { API_PROXY_TARGET: "http://127.0.0.1:8001" },
          url: "http://127.0.0.1:5173",
          timeout: 60000,
          reuseExistingServer: process.env.E2E_REUSE_SERVER === "true",
        },
      ],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
