// @ts-check
const { test, expect } = require('@playwright/test');

const keyFromEnv = process.env.GOOGLE_API_KEY;
const shouldSkip = !keyFromEnv;

console.log(`--- E2E Test Pre-flight Check ---`);
console.log(`Value of process.env.GOOGLE_API_KEY: "${keyFromEnv}"`);
console.log(`Type of process.env.GOOGLE_API_KEY: ${typeof keyFromEnv}`);
console.log(`Test will be skipped: ${shouldSkip}`);
console.log(`---------------------------------`);

// 從環境變數讀取使用者提供的 API 金鑰
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
const VIDEO_URL = "https://b23.tv/6FjXRsx";

// 只有在環境變數中明確提供了 API 金鑰時才執行此測試套件
test.describe.skip(shouldSkip, '使用者端對端流程：YouTube 報告生成', () => {

  test.beforeEach(async ({ page }) => {
    // 前往應用程式的 YouTube 報告頁面
    await page.goto('/youtube', { waitUntil: 'networkidle' });
  });

  test('使用 Bilibili 網址成功產生報告並驗證 UI', async ({ page }) => {
    // 由於這是一個真實的 API 測試，我們需要設定較長的超時時間
    test.setTimeout(300000); // 5 分鐘

    // --- 步驟 1: 設定 API 金鑰並驗證模型載入 ---
    console.log('[測試步驟 1] 正在設定 API 金鑰並等待模型列表載入...');
    await page.getByTestId('api-key-input').fill(GOOGLE_API_KEY);
    await page.getByTestId('save-api-key-button').click();

    // 等待"模型載入成功"的狀態訊息出現
    await expect(page.getByText('模型載入成功')).toBeVisible({ timeout: 20000 });
    console.log('[測試步驟 1] 金鑰驗證成功，模型列表已載入。');

    // --- 步驟 2: 選擇指定的 "Flash" 模型 ---
    console.log('[測試步驟 2] 正在選擇 "Flash" 模型...');
    const modelSelect = page.getByTestId('gemini-model-select');
    // 等待模型列表載入完成 (不再是"等待中"的選項)
    await expect(modelSelect.locator('option', { hasText: '等待從伺服器載入模型列表...' })).toHaveCount(0, { timeout: 10000 });

    // 尋找並選擇包含 "flash" 的模型 (忽略大小寫)
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
    console.log(`[測試步驟 2] 成功選擇模型: ${flashModelValue}`);

    // --- 步驟 3: 輸入 URL 並開始處理 ---
    console.log(`[測試步驟 3] 正在輸入網址 "${VIDEO_URL}" 並開始處理...`);
    await page.locator('.youtube-url-input').nth(0).fill(VIDEO_URL);
    await page.getByTestId('start-youtube-processing-button').click();

    // --- 步驟 4: 驗證最終報告是否出現 ---
    console.log('[測試步驟 4] 正在等待分析結果...');
    // 根據影片標題等待報告項目出現
    const reportItem = page.locator('#youtube-file-browser .task-item').filter({ hasText: /【JFla】一個人就是一支樂隊！/ });
    await expect(reportItem).toBeVisible({ timeout: 240000 });
    console.log('[測試步驟 4] 在報告瀏覽區找到已完成的項目。');

    // --- 步驟 5: 驗證操作按鈕 ---
    console.log('[測試步驟 5] 正在驗證操作按鈕是否存在...');
    await expect(reportItem.getByText('詳細資料')).toBeVisible();
    await expect(reportItem.getByText('預覽')).toBeVisible();
    await expect(reportItem.getByText('下載')).toBeVisible();
    console.log('[測試步驟 5] 所有操作按鈕均已正確顯示。');

    // --- 步驟 6: 截圖驗證 ---
    console.log('[測試步驟 6] 正在擷取最終狀態的螢幕截圖...');
    await page.screenshot({ path: 'youtube_flow_success.jpg', fullPage: true, quality: 90, type: 'jpeg' });
    console.log('[測試步驟 6] 螢幕截圖已儲存至 youtube_flow_success.jpg');

    // 額外驗證：點擊預覽，確保彈窗能正常工作
    await reportItem.getByText('預覽').click();
    await expect(page.getByTestId('report-modal')).toBeVisible();
    console.log('[額外驗證] 預覽彈窗功能正常。');
  });
});
