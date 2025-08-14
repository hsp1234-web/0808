// @ts-check
import { test, expect } from '@playwright/test';

// JULES'S FIX: Remove hardcoded URL
// const SERVER_URL = 'http://127.0.0.1:42649/';

test('take a simple screenshot for verification', async ({ page }) => {
  // Increase timeout for this specific test
  test.setTimeout(30000);

  // Go to the page
  await page.goto('/', { waitUntil: 'networkidle' });

  // Wait for the h1 to be visible
  await expect(page.locator('h1')).toContainText('音訊轉錄儀', { timeout: 10000 });

  // Wait for the websocket to be ready
  await page.waitForFunction(() => {
    return window.app && window.app.socket && window.app.socket.readyState === 1; // 1 means OPEN
  }, { timeout: 15000 });

  // Take the screenshot
  await page.screenshot({ path: 'visual-verification-screenshot.png' });
});
