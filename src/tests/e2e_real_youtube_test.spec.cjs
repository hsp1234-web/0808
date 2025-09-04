// @ts-check
const { test, expect } = require('@playwright/test');

// 從環境變數讀取 API 金鑰
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;

// 如果沒有金鑰，整個測試檔案將被跳過
test.describe.skip(!GOOGLE_API_KEY, '真實 YouTube API 整合測試 (需要有效的金鑰)', () => {
  const BILIBILI_URL = "https://b23.tv/xALqLQM";

  test.beforeEach(async ({ page }) => {
    // 前往應用程式的 YouTube 報告頁面
    // JULES'S FIX: The new URL is /youtube
    await page.goto('/youtube', { waitUntil: 'networkidle' });
  });

  test('成功載入 Gemini 模型並產生報告', async ({ page }) => {
    // 由於這是一個真實的 API 測試，我們需要設定較長的超時時間
    test.setTimeout(240000); // 4 分鐘

    // 1. 設定 API 金鑰並驗證模型載入
    await page.getByTestId('api-key-input').fill(GOOGLE_API_KEY);
    await page.getByTestId('save-api-key-button').click();

    // 等待"模型載入成功"的狀態訊息出現
    await expect(page.getByText('模型載入成功')).toBeVisible({ timeout: 20000 });

    const modelSelect = page.getByTestId('gemini-model-select');
    // 等待模型列表載入完成 (不再是"等待中"的選項)
    await expect(modelSelect.locator('option', { hasText: '等待從伺服器載入模型列表...' })).toHaveCount(0, { timeout: 10000 });

    // 選擇包含 "flash" 的模型
    const options = await modelSelect.locator('option').all();
    let flashModelValue;
    for (const option of options) {
        const text = await option.textContent();
        if (text && text.toLowerCase().includes('flash')) {
            flashModelValue = await option.getAttribute('value');
            break;
        }
    }
    if (!flashModelValue) {
        throw new Error('在模型列表中找不到包含 "flash" 的模型。');
    }
    await modelSelect.selectOption({ value: flashModelValue });
    console.log(`[Test] 成功選擇模型: ${flashModelValue}`);

    // 2. 輸入 URL 並開始處理
    await page.locator('.youtube-url-input').nth(0).fill(BILIBILI_URL);
    await page.getByTestId('start-youtube-processing-button').click();

    // 3. 驗證最終報告
    // 等待報告出現在瀏覽區
    const reportItem = page.locator('#youtube-file-browser .task-item').filter({ hasText: /十年了，B站變了嗎/ });
    await expect(reportItem).toBeVisible({ timeout: 240000 });
    console.log('[Test] 在報告瀏覽區找到已完成的項目。');

    // 點擊預覽
    await reportItem.getByTestId('view-report-button').click();
    await expect(page.getByTestId('report-modal')).toBeVisible();

    // 驗證 iframe 中的內容
    const iframe = page.frameLocator('#preview-modal iframe');
    await expect(iframe.locator('body')).toContainText(/AI (學習|分析)報告/, { timeout: 15000 });
    console.log('[Test] ✅ 預覽報告功能驗證成功。');

    // 關閉 Modal
    await page.locator('#modal-close-btn').click();
    await expect(page.getByTestId('report-modal')).not.toBeVisible();
  });
});
