// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

const JpgScreenshot = async (page, name) => {
  // Ensure the output directory exists
  const resultsDir = path.join('ai_test_reports', 'playwright_results');
  require('fs').mkdirSync(resultsDir, { recursive: true });
  await page.screenshot({ path: path.join(resultsDir, `${name}.jpg`), type: 'jpeg' });
};

test.describe('AI Visual Patrol and Core Functionality Test', () => {
  const BASE_URL = 'http://127.0.0.1:42649'; // Consistent with API_PORT in run_ai_visual_test.py

  test.beforeEach(async ({ page }) => {
    // Listen and log all console messages
    page.on('console', msg => console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`));
    // Listen and log all failed requests
    page.on('requestfailed', request => console.log(`[Network Fail] ${request.url()} ${request.failure()?.errorText}`));
    // Listen and log page errors
    page.on('pageerror', exception => console.log(`[Page Error] Unhandled exception: ${exception}`));
  });

  test('Step 1: Main Page Patrol', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await expect(page.locator('body')).toContainText('善狼'); // Keep Chinese text for content validation
    await JpgScreenshot(page, '01_main_page_patrol');
  });

  test('Step 2: MP3 Page Patrol', async ({ page }) => {
    await page.goto(`${BASE_URL}/static/mp3.html`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('MP3');
    await JpgScreenshot(page, '02_mp3_page_patrol');
  });

  test('Step 3: Prompts Page Patrol', async ({ page }) => {
    await page.goto(`${BASE_URL}/static/prompts.html`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('Prompts');
    await JpgScreenshot(page, '03_prompts_page_patrol');
  });

  test('Step 4: Download Tiny Model', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    const tinyModelButton = page.locator('button', { hasText: /tiny/i });
    await expect(tinyModelButton).toBeVisible();

    const buttonText = await tinyModelButton.innerText();
    if (!buttonText.includes('✅')) {
      console.log('Model not downloaded, clicking download...');
      await tinyModelButton.click();
      await expect(tinyModelButton).toContainText('✅', { timeout: 60000 });
      console.log('Model downloaded successfully!');
    } else {
      console.log('Model was already downloaded.');
    }

    await JpgScreenshot(page, '04_model_download_final_state');
  });

  test('Step 5: Upload Audio and Verify Transcription', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    const tinyModelButton = page.locator('button', { hasText: /tiny/i });
    await expect(tinyModelButton).toContainText('✅');

    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeVisible();

    const filePath = path.join(__dirname, 'fixtures', 'test_audio.mp3');
    await fileInput.setInputFiles(filePath);

    // Assuming button text is '開始轉錄'
    const submitButton = page.locator('button', { hasText: '開始轉錄' });
    await expect(submitButton).toBeVisible();
    await submitButton.click();

    // Assuming result is displayed in this area
    const resultArea = page.locator('#transcription-result');
    await expect(resultArea).not.toBeEmpty({ timeout: 60000 });

    // Assuming this is the expected audio content
    await expect(resultArea).toContainText('這是測試音訊');

    await JpgScreenshot(page, '05_transcription_result');
  });
});
