// @ts-check
import { test, expect } from '@playwright/test';

// JULES: This is the golden snapshot test.
// It will serve as the visual baseline for our application.
// Any future visual regression tests will compare against this snapshot.

test('golden snapshot', async ({ page }) => {
  // Navigate to the root of the web server
  await page.goto('/');

  // Wait for the main app container to be visible to ensure the page is loaded
  await expect(page.locator('#app')).toBeVisible();

  // Give a little extra time for any animations or late-loading elements to settle.
  await page.waitForTimeout(1000);

  // Take a full-page screenshot and compare it to the golden snapshot.
  // The first time this test is run, it will create the 'golden-snapshot.png' file.
  // Subsequent runs will compare against this file.
  await expect(page).toHaveScreenshot('golden-snapshot.png', {
    fullPage: true,
    maxDiffPixelRatio: 0.05, // Allow for minor rendering differences between machines
  });
});
