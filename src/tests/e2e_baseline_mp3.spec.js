// @ts-check
import { test, expect } from '@playwright/test';

/**
 * @file 該檔案為 `mp3.html` 頁面的基準 (Baseline) 端對端測試。
 * @description 此測試的目的是提供一個最基本、最快速的健康檢查，確保頁面的核心架構能被正確載入且主要UI元件可見。
 *              它不涉及複雜的使用者互動，只驗證初始狀態。
 */

// --- 測試設定 ---
const SERVER_URL = 'http://127.0.0.1:42649/'; // 來自 `run_server_for_playwright.py` 的埠號
const TEST_TIMEOUT = 30000; // 此測試的超時時間為 30 秒

// --- E2E 測試套件 ---

test.describe('基準測試: MP3 應用程式初始狀態驗證', () => {

  test.setTimeout(TEST_TIMEOUT);

  /**
   * @description 測試 `mp3.html` 頁面是否能成功載入並顯示核心UI元件。
   * 步驟:
   * 1. 導覽至應用程式主頁面。
   * 2. 驗證 WebSocket 是否成功連線，狀態文字應顯示「已連線」。
   * 3. 驗證三個主要的功能分頁按鈕都已正確渲染並可見。
   */
  test('頁面載入後應顯示「已連線」狀態與主要分頁標籤', async ({ page }) => {
    // 1. 導覽至主頁面
    await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });

    // 2. 驗證 WebSocket 連線狀態
    // 等待最多 15 秒，直到狀態文字包含「已連線」
    const statusText = page.locator('#status-text');
    await expect(statusText).toContainText('已連線', { timeout: 15000 });

    // 3. 驗證主要分頁按鈕是否可見
    const localFileTab = page.locator('button[data-tab="local-file-tab"]');
    const downloaderTab = page.locator('button[data-tab="downloader-tab"]');
    const youtubeReportTab = page.locator('button[data-tab="youtube-report-tab"]');

    await expect(localFileTab).toBeVisible();
    await expect(localFileTab).toContainText('本機檔案轉錄');

    await expect(downloaderTab).toBeVisible();
    await expect(downloaderTab).toContainText('媒體下載器');

    await expect(youtubeReportTab).toBeVisible();
    await expect(youtubeReportTab).toContainText('YouTube 轉報告');

    // 4. 測試成功，擷取螢幕截圖
    await page.screenshot({ path: 'e2e_baseline_success.jpg', fullPage: true });
  });
});
