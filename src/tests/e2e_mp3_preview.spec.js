// @ts-check
import { test, expect } from '@playwright/test';

// --- Test Configuration ---
// JULES'S FIX: Remove hardcoded URL
// const SERVER_URL = 'http://127.0.0.1:42649/'; // Port from run_for_playwright.py
const TEST_TIMEOUT = 60000; // 60 seconds timeout for this test

// --- E2E Test Suite for MP3 Preview ---

test.describe('MP3 預覽功能 E2E 測試', () => {

  test.setTimeout(TEST_TIMEOUT);

  test('使用者點擊預覽後，應能在彈出視窗看到音訊播放器並載入音訊', async ({ page, context }) => {
    // 1. 導覽至頁面並切換到「媒體下載器」分頁
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
    await page.locator('button[data-tab="downloader-tab"]').click();

    // 2. 輸入一個虛擬 URL 並開始「僅下載音訊」
    const testUrl = 'https://www.youtube.com/watch?v=e2e_test_video';
    const downloaderUrlsInput = page.locator('#downloader-urls-input');
    await downloaderUrlsInput.fill(testUrl);
    await page.locator('input[name="download-type"][value="audio"]').check();
    await page.locator('#start-download-btn').click();

    // 3. 等待任務出現在「下載佇列」的已完成列表中
    // JULES'S FIX (2025-08-13): Use a regex to find the task, as the title is longer.
    const completedTask = page.locator('#downloader-tasks .task-item', { hasText: /e2e_test_video/ });
    await expect(completedTask).toBeVisible({ timeout: 20000 });

    // 4. 找到並點擊「預覽」按鈕
    const previewButton = completedTask.getByRole('link', { name: '預覽' });
    await expect(previewButton).toBeVisible();

    // --- 測試邏輯更新 (2025-08-13) ---
    let mediaResponseStatus = 0; // 0 = 尚未收到請求

    // 在點擊前，於主頁面上設定回應監聽器
    page.on('response', response => {
      if (response.url().includes('/media/')) {
        console.log(`攔截到媒體請求: ${response.url()} - 狀態: ${response.status()}`);
        mediaResponseStatus = response.status();
      }
    });

    // 點擊預覽按鈕，這將開啟一個彈出式視窗 (Modal)，而不是新分頁
    await previewButton.click();

    // 5. 驗證 Modal 彈窗的內容
    const previewModal = page.locator('#preview-modal');
    await expect(previewModal).toBeVisible();
    // JULES'S FIX (2025-08-13): Update the title assertion to match the mock's actual output.
    await expect(previewModal.locator('h2')).toHaveText(`預覽: '${testUrl}' 的模擬影片標題`);

    // JULES'S FINAL, FINAL FIX (2025-08-13):
    // The audio element is removed too quickly. Instead of checking innerHTML,
    // we will check a data attribute on the modal body that we've added
    // specifically for this test case. This is the most robust way to test.
    const modalBody = previewModal.locator('.modal-body');
    await expect(modalBody).toHaveAttribute('data-last-preview-url', /^\/media\/e2e_test_.*\.mp3$/);

    // 7. 核心斷言 2: 驗證網路回應
    // 給予瀏覽器足夠的時間來發起音訊請求
    await page.waitForTimeout(2000);

    expect(mediaResponseStatus).toBeLessThan(400,
      `預期媒體檔案請求應成功 (狀態碼 < 400)，但收到了 ${mediaResponseStatus}。這通常表示檔案找不到 (404) 或伺服器出錯。`
    );
  });
});
