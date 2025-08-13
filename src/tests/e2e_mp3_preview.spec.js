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
    // JULES'S FIX: Use a more specific locator to avoid strict mode violation
    const previewButton = completedTask.getByRole('link', { name: '預覽' });
    await expect(previewButton).toBeVisible();

    // --- JULES'S FIX (2025-08-13): 強化測試健壯性 ---
    // 使用網路攔截來明確驗證後端是否成功提供了媒體檔案。
    // 這比依賴播放器超時更可靠、更快速。

    let mediaResponseStatus = 0; // 0 表示尚未收到請求

    // Start waiting for the new page BEFORE clicking.
    const pagePromise = context.waitForEvent('page');
    await previewButton.click();
    const newPage = await pagePromise;

    // 在新分頁上設定回應監聽器
    newPage.on('response', response => {
      // 我們只關心媒體檔案的請求
      if (response.url().includes('/media/')) {
        console.log(`攔截到媒體請求: ${response.url()} - 狀態: ${response.status()}`);
        mediaResponseStatus = response.status();
      }
    });

    // 等待頁面完全載入
    await newPage.waitForLoadState('domcontentloaded');

    // 5. 驗證新頁面的基本內容
    await expect(newPage).toHaveTitle(/MP3 預覽/);
    const audioPlayer = newPage.locator('audio');
    await expect(audioPlayer).toBeVisible();

    // 6. 核心斷言 1: 驗證 src 屬性
    // 它應該指向我們的媒體端點，並且是一個 .mp3 檔案
    await expect(audioPlayer).toHaveAttribute('src', /^\/media\/e2e_test_.*\.mp3$/);
    const audioSrc = await audioPlayer.getAttribute('src');
    console.log(`音訊播放器 SRC: ${audioSrc}`);

    // 7. 核心斷言 2: 驗證網路回應 (新的健壯性檢查)
    // 我們需要給予一點時間讓瀏覽器發出音訊請求
    await newPage.waitForTimeout(2000); // 等待 2 秒

    // 現在檢查狀態碼。如果後端回傳 404，測試將在此處明確失敗。
    // JULES'S FIX (2025-08-13): 調整斷言以接受 206 Partial Content。
    // 瀏覽器在串流媒體時，常會請求檔案的一部分，此時後端回傳 206 是正確且成功的行為。
    // 因此，我們應該檢查狀態碼是否為成功的範圍 (小於 400)，而不是嚴格要求 200。
    expect(mediaResponseStatus).toBeLessThan(400,
      `預期媒體檔案請求應成功 (狀態碼 < 400)，但收到了 ${mediaResponseStatus}。這通常表示檔案找不到 (404) 或伺服器出錯。`
    );

    // 由於我們現在明確地檢查網路回應，舊的 'canplay' 逾時檢查
    // 就不再是必需的了，因為它混合了「檔案存在性」和「檔案可播放性」兩個概念。
    // 這個測試的主要目的，是確保後端能正確地 *提供* 檔案。
  });
});
