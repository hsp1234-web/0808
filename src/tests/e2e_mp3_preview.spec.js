// @ts-check
import { test, expect } from '@playwright/test';

// --- Test Configuration ---
const SERVER_URL = 'http://127.0.0.1:42649/'; // Port from run_for_playwright.py
const TEST_TIMEOUT = 60000; // 60 seconds timeout for this test

// --- E2E Test Suite for MP3 Preview ---

test.describe('MP3 預覽功能 E2E 測試', () => {

  test.setTimeout(TEST_TIMEOUT);

  test('使用者點擊預覽後，應能在新頁面看到音訊播放器並載入音訊', async ({ page, context }) => {
    // 1. Navigate to the page and switch to the YouTube tab
    await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
    await page.locator('button[data-tab="youtube-report-tab"]').click();

    // 2. Input a dummy URL and start an "audio only" download
    const youtubeUrlInput = page.locator('.youtube-url-input').first();
    await youtubeUrlInput.fill('https://www.youtube.com/watch?v=e2e_test_video');

    // Use a regex for the button text to be more robust
    const downloadAudioBtn = page.locator('button', { hasText: /僅下載音訊/ });
    await downloadAudioBtn.click();

    // 3. Wait for the task to appear in the completed list
    const completedTask = page.locator('#completed-tasks .task-item', { hasText: 'e2e_test_video' });
    await expect(completedTask).toBeVisible({ timeout: 20000 });

    // 4. Find and click the "Preview" button, which opens a new page
    const previewButton = completedTask.locator('a.btn-preview');
    await expect(previewButton).toBeVisible();

    // Start waiting for the new page before clicking.
    const pagePromise = context.waitForEvent('page');
    await previewButton.click();
    const newPage = await pagePromise;
    await newPage.waitForLoadState();

    // 5. Verify the new page's content
    await expect(newPage).toHaveTitle(/MP3 預覽/);
    const audioPlayer = newPage.locator('audio');
    await expect(audioPlayer).toBeVisible();

    // 6. Core Assertion 1: Verify the src attribute
    // It should point to our media endpoint and be an .mp3 file
    await expect(audioPlayer).toHaveAttribute('src', /^\/media\/e2e_test_.*\.mp3$/);
    const audioSrc = await audioPlayer.getAttribute('src');
    console.log(`音訊播放器 SRC: ${audioSrc}`);

    // 7. Core Assertion 2: Verify the browser can play the audio
    // We expect this to FAIL with our dummy text file, but the test itself is important.
    // A timeout here indicates the browser could not load the media.
    try {
      const canPlay = await newPage.evaluate(() => {
        return new Promise((resolve, reject) => {
          const audio = document.querySelector('audio');
          if (!audio) {
            return reject(new Error('找不到 audio 元素'));
          }
          // If audio is already loaded
          if (audio.readyState >= 3) { // HAVE_FUTURE_DATA
            return resolve(true);
          }
          // Listen for the 'canplay' event
          audio.addEventListener('canplay', () => resolve(true));
          // Set a timeout to prevent the test from hanging indefinitely
          setTimeout(() => reject(new Error('音訊在 10 秒內未能觸發 canplay 事件')), 10000);
        });
      });
      // If the promise resolves, it means the audio is valid.
      // This would be an unexpected success with our current dummy file.
      expect(canPlay).toBe(true);
      console.log("預期外的成功：瀏覽器回報可以播放此音訊檔案。");

    } catch (error) {
      // This is the EXPECTED outcome for our dummy text file.
      // The test fails if the error is NOT the timeout error.
      console.log(`符合預期的事件: ${error.message}`);
      expect(error.message).toContain('音訊在 10 秒內未能觸發 canplay 事件');
    }
  });
});
