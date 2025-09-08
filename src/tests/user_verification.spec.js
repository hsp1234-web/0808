// @ts-check
import { test, expect } from '@playwright/test';

// 使用者提供的 API 金鑰和測試網址
const USER_API_KEY = 'AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU';
const BILIBILI_URL = 'https://b23.tv/M5MwbVx';

test.describe('綜合功能驗證測試', () => {
  // 在所有測試開始前，先設定好環境
  test.beforeEach(async ({ page }) => {
    // 設置一個較長的超時時間，因為媒體下載和 AI 分析可能需要時間
    test.setTimeout(300000); // 5 分鐘
    // 導覽至首頁 (媒體下載器)
    await page.goto('/');
    // 等待頁面核心元素載入，確保頁面已就緒
    await expect(page.locator('h2:has-text("媒體下載器")')).toBeVisible();
  });

  test('儀表板、縮放、Gemini模型和媒體下載功能驗證', async ({ page }) => {
    // --- 1. 驗證儀表板數據 ---
    await page.waitForTimeout(3000); // 等待幾秒讓系統數據更新
    const cpuUsage = await page.locator('#cpu-label').textContent();
    const ramUsage = await page.locator('#ram-label').textContent();
    expect(cpuUsage).not.toBe('--%');
    expect(ramUsage).not.toBe('--%');
    await page.screenshot({ path: 'verification_01_dashboard_working.jpg' });

    // --- 2. 驗證縮放按鈕 ---
    const fontSizeDisplay = page.locator('#font-size-display');
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');
    await page.screenshot({ path: 'verification_02_zoom_in.jpg' });
    await page.locator('#zoom-out-btn').click();
    await expect(fontSizeDisplay).toHaveText('100%');
    await page.screenshot({ path: 'verification_03_zoom_out.jpg' });

    // --- 3. 驗證 Gemini 模型列表 ---
    await page.getByRole('link', { name: '▶️ YouTube 轉報告' }).click();
    await expect(page.locator('h2:has-text("Google API 金鑰管理")')).toBeVisible();

    // 輸入並儲存 API 金鑰
    await page.locator('[data-testid="api-key-input"]').fill(USER_API_KEY);
    await page.locator('[data-testid="save-api-key-button"]').click();

    // 等待並驗證模型列表
    await expect(page.locator('#api-key-status > span')).toHaveText('金鑰有效，Gemini 功能已啟用', { timeout: 20000 });
    const flashModelOption = page.locator('option[value="models/gemini-1.5-flash"]');
    await expect(flashModelOption).toBeVisible({ timeout: 15000 });
    await expect(flashModelOption).toHaveText('Gemini 1.5 Flash');
    await page.screenshot({ path: 'verification_04_gemini_models_loaded.jpg' });

    // --- 4. 驗證媒體下載 (音訊) ---
    await page.getByRole('link', { name: '📥 媒體下載器' }).click();
    await expect(page.locator('h2:has-text("媒體下載器")')).toBeVisible();

    await page.locator('#downloader-urls-input').fill(BILIBILI_URL);
    await page.locator('input[name="download-type"][value="audio"]').check();
    await page.locator('#start-download-btn').click();

    // 等待音訊下載任務完成
    const audioTask = page.locator('.task-item', { hasText: '【 bilibili】' }).first();
    await expect(audioTask.locator('[data-testid="view-report-button"]')).toBeVisible({ timeout: 180000 });
    await expect(audioTask.locator('.btn-download')).toBeVisible();
    await page.screenshot({ path: 'verification_05_audio_download_complete.jpg' });

    // --- 5. 驗證媒體下載 (影片) ---
    await page.locator('#downloader-urls-input').fill(BILIBILI_URL);
    await page.locator('input[name="download-type"][value="video"]').check();
    await page.locator('#start-download-btn').click();

    // 等待影片下載任務完成
    const videoTask = page.locator('.task-item', { hasText: '【 bilibili】' }).last();
    await expect(videoTask.locator('[data-testid="view-report-button"]')).toBeVisible({ timeout: 180000 });
    await expect(videoTask.locator('.btn-download')).toBeVisible();
    await page.screenshot({ path: 'verification_06_video_download_complete.jpg' });
  });
});
