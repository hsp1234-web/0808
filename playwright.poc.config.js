// playwright.poc.config.js
// 繁體中文註解：這是一個專為 POC 系統測試而建立的 Playwright 設定檔。
// 它與主要的設定檔完全相同，但移除了 webServer 區塊，
// 因為我們將手動啟動我們自己的 FastAPI 伺服器 (main.py)。

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Timeout for each test, includes hooks. 3 minutes.
  timeout: 180000,

  testDir: './src/tests',
  fullyParallel: false,
  workers: 1,

  expect: {
    // Timeout for expect() assertions.
    timeout: 10000,
  },

  reporter: 'list',

  // 繁體中文註解：webServer 區塊已被刻意移除。
  // webServer: { ... },

  use: {
    // 繁體中文註解：由於沒有 webServer，我們需要提供一個基礎 URL。
    // 但是，我們的測試腳本中使用了絕對 URL (http://127.0.0.1:8000/)，
    // 所以這個 baseURL 不會被實際使用，但保留它以維持結構完整性。
    baseURL: 'http://127.0.0.1:8000',

    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
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
