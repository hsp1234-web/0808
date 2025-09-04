// playwright.config.v2.js
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  // Timeout for each test, includes hooks. 3 minutes.
  timeout: 180000,

  testDir: "./src/tests", // 指向 v2 測試目錄

  // JULES'S FIX (2025-09-03): Explicitly define all test file patterns to be included.
  // The default pattern only looks for *.spec.js, but our v2 tests are named *.spec_v2.js.
  testMatch: ["**/*.spec.js", "**/*.spec_v2.js", "**/*.spec_v2.cjs"],

  fullyParallel: false,
  workers: 1,

  expect: {
    timeout: 10000,
  },

  reporter: "list",

  // 使用 v2 的伺服器啟動腳本
  webServer: {
    command: "python3 scripts/run_server_for_playwright_v2.py",
    url: "http://127.0.0.1:42650/", // 使用 v2 的埠號，改用根路徑進行健康檢查
    reuseExistingServer: !process.env.CI,
    timeout: 70 * 1000,
  },

  use: {
    baseURL: "http://127.0.0.1:42650", // 使用 v2 的埠號

    trace: "on-first-retry",
  },

  // JULES: Configure projects for major browsers with sandbox disabled
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Add arguments to make it work in sandboxed environments like Docker/CI
        launchOptions: {
          args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
          ],
        },
      },
    },
  ],
});
