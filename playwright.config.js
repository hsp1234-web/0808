// playwright.config.js
import { defineConfig } from '@playwright/test';

export default defineConfig({
  // Timeout for each test, includes hooks. 3 minutes.
  timeout: 180000,

  expect: {
    // Timeout for expect() assertions.
    timeout: 10000,
  },

  // Reporter to use. See https://playwright.dev/docs/test-reporters
  reporter: 'list',

  use: {
    // Base URL to use in actions like `await page.goto('/')`.
    baseURL: 'http://127.0.0.1:3000',

    // Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer
    trace: 'on-first-retry',
  },
});
