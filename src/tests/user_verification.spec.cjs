// @ts-check
const { test, expect } = require('@playwright/test');

const BILI_URL = 'https://b23.tv/M5MwbVx';
const USER_API_KEY = 'AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU';
const MOCK_BILI_TITLE = '【bilibili】'; // The title that the mock downloader returns

test.describe('使用者指定功能驗證', () => {

  test.beforeEach(async ({ page }) => {
    // 每次測試前都先導航到主頁面並清理環境
    // 使用真實 API 時，清理 DB 很重要
    await page.goto('/');
    await page.request.post('/api/debug/clear_tasks');
    await expect(page.getByRole('heading', { name: '音訊轉錄儀' })).toBeVisible({ timeout: 10000 });
  });

  // 測試案例 1：影音下載
  test('應能成功下載 Bilibili 影片的音訊和影片', async ({ page }) => {
    test.setTimeout(5 * 60 * 1000); // 5 分鐘超時

    // 1. 導航至媒體下載器分頁
    await page.getByRole('link', { name: '📥 媒體下載器' }).click();
    await expect(page.getByRole('heading', { name: '媒體下載器' })).toBeVisible();

    const urlsInput = page.locator('#downloader-urls-input');
    const startDownloadBtn = page.locator('#start-download-btn');
    const tasksContainer = page.locator('#downloader-tasks');

    // 2. 下載音訊
    await urlsInput.fill(BILI_URL);
    await page.getByLabel('純音訊').check();
    await startDownloadBtn.click();

    // 等待第一個任務出現並完成
    const audioTask = tasksContainer.locator('.task-item').first();
    await expect(audioTask).toBeVisible({ timeout: 20000 });
    // This now waits for the 'Preview' button, which is the ultimate sign of completion
    await expect(audioTask.locator('.btn-preview')).toBeVisible({ timeout: 4 * 60 * 1000 });

    // 3. 下載影片
    await urlsInput.fill(BILI_URL);
    await page.getByLabel('影片').check();
    await startDownloadBtn.click();

    // 等待第二個任務出現並完成
    await expect(tasksContainer.locator('.task-item')).toHaveCount(2, { timeout: 20000 });
    const videoTask = tasksContainer.locator('.task-item').first(); // The newest task appears at the top
    await expect(videoTask.locator('.btn-preview')).toBeVisible({ timeout: 4 * 60 * 1000 });

    // 4. 產生截圖
    await page.screenshot({ path: 'download_success.jpg', fullPage: true });
    console.log('Screenshot for download success has been taken.');
  });

  // 測試案例 2：縮放按鈕與模型列表
  test('應能成功載入模型列表並正常使用縮放按鈕', async ({ page }) => {
    test.setTimeout(2 * 60 * 1000); // 2 分鐘超時

    // 1. 導航至 YouTube 轉報告分頁
    await page.getByRole('link', { name: '▶️ YouTube 轉報告' }).click();
    await expect(page.getByRole('heading', { name: 'Google API 金鑰管理' })).toBeVisible();

    // 2. 輸入 API Key 並驗證
    await page.getByPlaceholder('在此貼上您的 Google API 金鑰').fill(USER_API_KEY);
    await page.getByRole('button', { name: '儲存金鑰' }).click();

    // 3. 等待模型列表載入並截圖
    await expect(page.locator('#api-key-status > span')).toHaveText('驗證成功', { timeout: 30000 });
    // JULES'S FIX: Add a wait for the select element to be enabled before checking its options.
    await expect(page.locator('#gemini-model-select')).toBeEnabled({ timeout: 10000 });
    // 確保下拉選單中至少有一個 "Flash" 模型選項
    const flashModelOption = page.locator('option', { hasText: /Flash/ });
    // JULES'S FIX: Instead of checking visibility which can be flaky,
    // assert that the option has been added to the DOM by checking the count.
    await expect(flashModelOption).toHaveCount(1, { timeout: 15000 });
    await page.screenshot({ path: 'model_list_populated.jpg', fullPage: true });
    console.log('Screenshot for model list populated has been taken.');

    // 4. 驗證縮放功能
    const fontSizeDisplay = page.locator('#font-size-display');
    await expect(fontSizeDisplay).toHaveText('100%');

    // 放大
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');

    // 再次放大
    await page.locator('#zoom-in-btn').click();
    await expect(fontSizeDisplay).toHaveText('120%');

    // 縮小
    await page.locator('#zoom-out-btn').click();
    await expect(fontSizeDisplay).toHaveText('110%');

    // 5. 產生最終截圖
    await page.screenshot({ path: 'zoom_buttons_work.jpg', fullPage: true });
    console.log('Screenshot for zoom buttons work has been taken.');
  });
});
