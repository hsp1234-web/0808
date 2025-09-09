// @ts-check
import { test, expect } from '@playwright/test';

// 使用者提供的 API 金鑰和測試網址
const USER_API_KEY = 'AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU';
const BILIBILI_URL = 'https://b23.tv/M5MwbVx';
// 後端 mock downloader 回傳的標題
const MOCK_BILIBILI_TITLE = '【 bilibili】';

test.describe('使用者功能驗證測試', () => {

  // 為所有測試設定較長的超時時間，因為媒體下載和 AI 分析可能需要時間
  test.setTimeout(300000); // 5 分鐘

  // 在每個測試開始前，先導覽至首頁
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1:has-text("音訊轉錄儀")')).toBeVisible();
  });

  test('測試案例 1：媒體下載器功能驗證', async ({ page }) => {
    // 導覽至媒體下載器頁面 (雖然是首頁，但點擊以確保狀態正確)
    await page.getByRole('link', { name: '📥 媒體下載器' }).click();
    await expect(page.locator('h2:has-text("媒體下載器")')).toBeVisible();

    // 填入網址並選擇音訊下載
    await page.locator('#downloader-urls-input').fill(BILIBILI_URL);
    await page.locator('input[name="download-type"][value="audio"]').check();
    await page.locator('#start-download-btn').click();

    // 驗證「處理中」狀態
    const audioTask = page.locator('.task-item', { hasText: MOCK_BILIBILI_TITLE }).first();
    // 檢查是否有「下載中」的狀態文字
    await expect(audioTask.locator('.task-status.status-downloading')).toBeVisible({ timeout: 15000 });

    // 等待音訊下載任務完成並驗證結果
    // 修正了選擇器，使用 .btn-preview
    await expect(audioTask.locator('.btn-preview')).toBeVisible({ timeout: 180000 });
    await expect(audioTask.locator('.btn-download')).toBeVisible();

    // 驗證「處理中」狀態消失
    await expect(audioTask.locator('.task-status.status-downloading')).not.toBeVisible();

    // 截圖證明
    await page.screenshot({ path: 'media_downloader_task_completed.jpg', fullPage: true });
  });

  test('測試案例 2：YouTube 報告與縮放功能驗證', async ({ page }) => {
    // 導覽至 YouTube 轉報告頁面
    await page.getByRole('link', { name: '▶️ YouTube 轉報告' }).click();
    await expect(page.locator('h2:has-text("Google API 金鑰管理")')).toBeVisible();

    // --- 驗證縮放按鈕 ---
    const fontSizeDisplay = page.locator('#font-size-display');
    await expect(fontSizeDisplay).toHaveText('100%');
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');
    await page.locator('#zoom-out-btn').click();
    await expect(fontSizeDisplay).toHaveText('100%');
    // 截圖證明縮放功能
    await page.screenshot({ path: 'youtube_report_zoom_buttons.jpg', fullPage: true });

    // --- 驗證 Gemini 模型與分析流程 ---
    // 輸入並儲存 API 金鑰
    await page.locator('[data-testid="api-key-input"]').fill(USER_API_KEY);
    await page.locator('[data-testid="save-api-key-button"]').click();

    // 等待並驗證模型列表
    // 根據 youtube_report.html 的程式碼，成功時的文字是「驗證成功」
    await expect(page.locator('#api-key-status > span')).toHaveText('驗證成功', { timeout: 20000 });
    // 根據使用者要求選擇 "2.0 Flash" 模型，其在系統中的 ID 為 'models/gemini-1.5-flash-latest'
    const flashModelOption = page.locator('option[value="models/gemini-1.5-flash-latest"]');
    await expect(flashModelOption).toBeVisible({ timeout: 15000 });

    // 選擇模型
    await page.locator('[data-testid="gemini-model-select"]').selectOption({ value: 'models/gemini-1.5-flash-latest' });

    // 輸入網址並啟動分析
    await page.locator('.youtube-url-input').first().fill(BILIBILI_URL);
    await page.locator('[data-testid="start-youtube-processing-button"]').click();

    // 驗證「處理中」狀態
    const reportTask = page.locator('.task-item', { hasText: MOCK_BILIBILI_TITLE }).first();
    // 檢查是否有「下載中」或「分析中」的狀態文字
    await expect(reportTask.locator('.task-status.status-downloading, .task-status.status-processing')).toBeVisible({ timeout: 15000 });

    // 等待分析任務完成並驗證結果
    await expect(reportTask.locator('[data-testid="view-report-button"]')).toBeVisible({ timeout: 180000 });

    // 驗證「處理中」狀態消失
    await expect(reportTask.locator('.task-status.status-downloading, .task-status.status-processing')).not.toBeVisible();

    // 截圖證明
    await page.screenshot({ path: 'youtube_report_task_completed.jpg', fullPage: true });
  });
});
