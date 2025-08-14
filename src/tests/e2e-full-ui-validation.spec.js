// @ts-check
import { test, expect } from '@playwright/test';

// --- 測試設定 ---
const SERVER_URL = 'http://127.0.0.1:42649/'; // 假設這是 local_run.py 啟動的伺服器位址
const TEST_TIMEOUT = 60000; // 60 秒

/**
 * 輔助函式：等待 WebSocket 連線成功
 * @param {import('@playwright/test').Page} page
 */
const waitForWebSocket = async (page) => {
  // JULES'S FIX (Attempt 2): Waiting for the 'websocket' event seems flaky/racy in this environment.
  // The new strategy is to poll the application's internal state directly from the browser context,
  // which is more reliable than event listening.
  await page.waitForFunction(() => {
    // We exposed the `app` instance to `window` in main.js for this purpose.
    return window.app && window.app.socket && window.app.socket.readyState === 1; // 1 means OPEN
  }, { timeout: 15000 });
};

// --- 全面 UI 驗證測試套件 ---
test.describe('全面 UI 功能驗證', () => {
  test.setTimeout(TEST_TIMEOUT);

  // 每次測試前，重新載入頁面並等待連線
  test.beforeEach(async ({ page }) => {
    // JULES'S DEBUGGING: Add a console listener to see what's happening inside the browser.
    page.on('console', msg => {
      console.log(`[Browser Console] ${msg.type().toUpperCase()}: ${msg.text()}`);
    });

    await page.goto(SERVER_URL, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('音訊轉錄儀');
    await waitForWebSocket(page);

    // JULES: Add a final screenshot command to provide visual proof to the user.
    // This will only run if the above assertions (including waitForWebSocket) pass.
    await page.screenshot({ path: 'test-results/final-screenshot.png' });
  });

  // 測試 1: 縮放功能與主要分頁切換
  test('應能正確縮放字體並切換分頁', async ({ page }) => {
    const fontSizeDisplay = page.locator('#font-size-display');

    // 驗證初始字體大小
    await expect(fontSizeDisplay).toHaveText('100%');

    // 測試放大
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('120%');

    // 測試縮小
    await page.locator('#zoom-out-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');
    await page.locator('#zoom-out-btn').click();
    await expect(fontSizeDisplay).toHaveText('100%');

    // 測試分頁切換
    const localFileTab = page.locator('#local-file-tab');
    const downloaderTab = page.locator('#downloader-tab');
    const youtubeReportTab = page.locator('#youtube-report-tab');

    // 初始狀態
    await expect(localFileTab).toBeVisible();
    await expect(downloaderTab).not.toBeVisible();
    await expect(youtubeReportTab).not.toBeVisible();

    // 切換到媒體下載器
    await page.locator('button[data-tab="downloader-tab"]').click();
    await expect(localFileTab).not.toBeVisible();
    await expect(downloaderTab).toBeVisible();
    await expect(youtubeReportTab).not.toBeVisible();

    // 切換到 YouTube 轉報告
    await page.locator('button[data-tab="youtube-report-tab"]').click();
    await expect(localFileTab).not.toBeVisible();
    await expect(downloaderTab).not.toBeVisible();
    await expect(youtubeReportTab).toBeVisible();

    // 切換回本機檔案
    await page.locator('button[data-tab="local-file-tab"]').click();
    await expect(localFileTab).toBeVisible();
    await expect(downloaderTab).not.toBeVisible();
    await expect(youtubeReportTab).not.toBeVisible();
  });

  // 測試 2: 媒體下載器介面互動
  test('媒體下載器應能正確響應 UI 互動', async ({ page }) => {
    // 切換到媒體下載器分頁
    await page.locator('button[data-tab="downloader-tab"]').click();

    const audioOptions = page.locator('#audio-options');
    const videoOptions = page.locator('#video-options');
    const removeSilenceCheckbox = page.locator('#remove-silence-checkbox');

    // 初始狀態應為純音訊
    await expect(audioOptions).toBeVisible();
    await expect(videoOptions).not.toBeVisible();
    await expect(removeSilenceCheckbox).toBeEnabled();

    // 切換到影片
    await page.locator('input[name="download-type"][value="video"]').click();
    await expect(audioOptions).not.toBeVisible();
    await expect(videoOptions).toBeVisible();
    await expect(removeSilenceCheckbox).toBeDisabled();

    // 切換回音訊
    await page.locator('input[name="download-type"][value="audio"]').click();
    await expect(audioOptions).toBeVisible();
    await expect(videoOptions).not.toBeVisible();
    await expect(removeSilenceCheckbox).toBeEnabled();

    // 測試輸入並開始下載
    await page.locator('#downloader-urls-input').fill('https://youtube.com/shorts/eIAg2P5rHmw');
    await page.locator('#start-download-btn').click();

    // 驗證任務已加入佇列
    const downloaderTasks = page.locator('#downloader-tasks');
    await expect(downloaderTasks.locator('.task-item')).toBeVisible();
    await expect(downloaderTasks.locator('.task-filename')).toContainText('https://youtube.com/shorts/eIAg2P5rHmw');
  });

  // 測試 3: YouTube 轉報告介面互動
  test('YouTube 轉報告頁面應能正確響應 UI 互動', async ({ page }) => {
    // 切換到 YouTube 轉報告分頁
    await page.locator('button[data-tab="youtube-report-tab"]').click();

    const youtubeLinkList = page.locator('#youtube-link-list');

    // 測試新增一列
    await expect(youtubeLinkList.locator('.youtube-link-row')).toHaveCount(1);
    await page.locator('#add-youtube-row-btn').click();
    await expect(youtubeLinkList.locator('.youtube-link-row')).toHaveCount(2);

    // 測試移除一列
    await youtubeLinkList.locator('.remove-youtube-row-btn').last().click();
    await expect(youtubeLinkList.locator('.youtube-link-row')).toHaveCount(1);

    // 測試 API 金鑰儲存
    const apiKeyStatus = page.locator('#api-key-status > span');
    await expect(apiKeyStatus).toHaveText('尚未提供金鑰');
    await page.locator('#api-key-input').fill('DUMMY-KEY-FOR-TESTING');
    await page.locator('#save-api-key-btn').click();
    // 由於是模擬模式，應該會顯示驗證成功
    await expect(apiKeyStatus).toContainText('金鑰有效', { timeout: 10000 });

    // 測試清除金鑰
    await page.locator('#clear-api-key-btn').click();
    await expect(apiKeyStatus).toHaveText('尚未提供金鑰');
  });

  // 測試 4: 日誌檢視器互動
  test('日誌檢視器應能獲取日誌並響應篩選', async ({ page }) => {
    const logOutput = page.locator('#log-output');
    const initialText = await logOutput.textContent();

    // 點擊更新日誌
    await page.locator('#fetch-logs-btn').click();

    // 等待日誌內容更新
    await expect(logOutput).not.toHaveText(initialText, { timeout: 10000 });
    const updatedText = await logOutput.textContent();
    expect(updatedText.length).toBeGreaterThan(0);

    // 測試篩選功能 (取消勾選 INFO)
    await page.locator('input[name="log-level"][value="INFO"]').uncheck();
    await page.locator('#fetch-logs-btn').click();

    // 等待日誌內容再次更新
    await expect(logOutput).not.toHaveText(updatedText, { timeout: 10000 });
    const filteredText = await logOutput.textContent();
    // 在模擬環境中，可能沒有非 INFO 的日誌，所以我們只斷言它不等於之前的內容
    // 在真實環境中，可以斷言不包含 '[INFO]'
    expect(filteredText).not.toContain('[INFO]');
  });
});
