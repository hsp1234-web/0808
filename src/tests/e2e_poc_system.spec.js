// 繁體中文註解：這是一個端對端測試腳本，用於驗證新的 POC 系統。
// 它會啟動一個瀏覽器，訪問 poc_test.html，提交任務，並驗證 WebSocket 的更新。
// 第四次嘗試：使用正確的 ESM 語法，並將使用 --no-web-server 旗標來執行。

import { test, expect } from '@playwright/test';

test.describe('POC 系統端對端測試', () => {

  test('應該能成功提交任務並透過 WebSocket 接收到完整的狀態更新', async ({ page }) => {
    const BILI_URL = 'https://b23.tv/hfLcdhf';
    // !! 重要提示 !!
    // 此 API 金鑰由使用者提供，僅用於此次測試。
    // 在實際的程式碼提交中，不應包含硬編碼的金鑰。
    const API_KEY = 'AIzaSyBdw0gY2oh2W_r1eN3ALzK9RCAAcedgF3E';

    // 增加測試的超時時間，因為整個流程（下載、轉錄、分析）可能需要幾分鐘
    test.setTimeout(300000); // 5 分鐘

    // 1. 導航到測試頁面
    // baseURL 由 playwright.config.js 提供，因此我們使用相對路徑
    await page.goto('/');

    // 驗證頁面標題
    await expect(page).toHaveTitle(/後端 POC 測試介面/);

    // 2. 填寫表單
    await page.locator('#youtube-url').fill(BILI_URL);
    await page.locator('#api-key').fill(API_KEY);

    // 3. 點擊提交按鈕
    await page.locator('#submit-btn').click();

    // 4. 驗證 WebSocket 狀態更新
    const statusContainer = page.locator('#status-container');

    // 等待並驗證初始訊息
    await expect(statusContainer).toContainText('✅ WebSocket 連線成功！準備提交任務...', { timeout: 10000 });
    await expect(statusContainer).toContainText(/🚀 任務已成功提交到後端。任務 ID:/, { timeout: 10000 });

    // 等待並驗證處理流程中的各個狀態
    await expect(statusContainer).toContainText('[狀態: downloading]', { timeout: 60000 });
    await expect(statusContainer).toContainText('[狀態: download_completed]', { timeout: 120000 });
    await expect(statusContainer).toContainText('[狀態: transcribing]', { timeout: 60000 });
    await expect(statusContainer).toContainText('[狀態: transcription_completed]', { timeout: 180000 });
    await expect(statusContainer).toContainText('[狀態: analyzing]', { timeout: 60000 });
    await expect(statusContainer).toContainText('[狀態: analysis_completed]', { timeout: 120000 });

    // 最終等待 "completed" 狀態
    await expect(statusContainer).toContainText('[狀態: completed]', { timeout: 120000 });
    await expect(statusContainer).toContainText(/報告路徑:/, { timeout: 5000 });

    // 5. 擷取最終結果的螢幕截圖
    // 根據使用者提醒，儲存為 jpg 格式
    const screenshotPath = 'poc_test_success.jpg';
    await page.screenshot({ path: screenshotPath, type: 'jpeg' });

    console.log(`✅ 測試成功！最終狀態截圖已儲存至: ${screenshotPath}`);

    // 驗證提交按鈕在任務結束後是否已重新啟用
    await expect(page.locator('#submit-btn')).toBeEnabled();
  });

});
