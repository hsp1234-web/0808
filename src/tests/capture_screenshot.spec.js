import { test, expect } from '@playwright/test';

test('Capture homepage screenshot', async ({ page }) => {
  // Navigate to the root URL, which is configured as http://127.0.0.1:42649 in playwright.config.js
  await page.goto('/');

  // Wait for a specific element to be visible to ensure the page is loaded
  // Looking at the html file, there is a tab container with id "tabs"
  await expect(page.locator('#tabs')).toBeVisible();

  // Take a screenshot
  await page.screenshot({ path: 'homepage_snapshot.png' });
});
