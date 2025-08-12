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

  use: {
    // JULES'S FIX: Set the correct baseURL for the test server
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
