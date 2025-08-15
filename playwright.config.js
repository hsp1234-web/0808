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

  // 修正：使用自訂的 shell 腳本來啟動和關閉後端服務，以解決子進程殘留的問題。
  // 這個腳本確保當 Playwright 結束測試時，所有相關的服務都會被優雅地終止。
  webServer: {
    command: 'bash scripts/run_server_for_e2e.sh',
    url: 'http://127.0.0.1:42649/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000, // 2 分鐘啟動超時
    // 增加一個關閉超時，讓我們的 trap 有時間執行
    killTimeout: 5000,
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
