// playwright.config.js
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Timeout for each test, includes hooks. 3 minutes.
  timeout: 180000,

  testDir: './src/tests', // JULES'S ADDITION: Explicitly set test directory
  fullyParallel: false, // JULES'S FIX: Run tests serially
  workers: 1, // JULES'S FIX: Force serial execution to prevent test pollution

  expect: {
    // Timeout for expect() assertions.
    timeout: 10000,
  },

  // Reporter to use. See https://playwright.dev/docs/test-reporters
  reporter: 'list',

  // JULES'S FIX: 使用一個穩健的 Python 腳本來管理後端服務的完整生命週期。
  // 這個腳本從 local_run.py 借鑒了經驗，包含了事前清理、依賴安裝、
  // 使用 Circus 進行程序管理，以及優雅的信號處理和關閉機制。
  // 這將從根本上解決服務啟動不穩定和掛起的問題。
  webServer: {
    // 指向新的 FastAPI POC 伺服器
    command: 'uvicorn src.main:app --host 0.0.0.0 --port 42649',
    // 使用一個新的健康檢查端點
    url: 'http://127.0.0.1:42649/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },

  use: {
    // The base URL is now provided by the webServer option.
    baseURL: 'http://127.0.0.1:42649',

    // Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer
    trace: 'on-first-retry',
  },

  // JULES: Configure projects for major browsers with sandbox disabled
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Add arguments to make it work in sandboxed environments like Docker/CI
        launchOptions: {
          args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
          ],
        },
      },
    },
  ],
});
