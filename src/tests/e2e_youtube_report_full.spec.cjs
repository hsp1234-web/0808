// @ts-check
const { test, expect } = require('@playwright/test');

// 使用者提供的金鑰和測試參數
const USER_API_KEY = 'AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU';
const YOUTUBE_URL = 'https://youtube.com/shorts/mG5z-pfhIiA?si=rIHZPsD_VpbgGeFt';
const BILIBILI_URL = 'https://b23.tv/xALqLQM';
const TARGET_MODEL_NAME = 'Gemini 1.5 Flash (模擬)'; // JULES'S FIX: Align with mock API response
const TARGET_MODEL_ID = 'models/gemini-1.5-flash-latest'; // 這通常是 UI 顯示名稱對應的後端 ID

test.describe('完整 YouTube 報告生成流程測試', () => {

  test.beforeEach(async ({ page }) => {
    // 每次測試前都先導航到主頁面
    await page.goto('/');
    // 清理資料庫，確保測試環境乾淨
    const response = await page.request.post('/api/debug/clear_tasks');
    await expect(response.ok()).toBeTruthy();
    // 等待核心系統就緒，這裡我們等待主標題出現，表示頁面已成功載入
    await expect(page.getByRole('heading', { name: '音訊轉錄儀' })).toBeVisible({ timeout: 10000 });
  });

  test('應能成功處理多個 URL、驗證所有 UI 元素並產生報告', async ({ page }) => {
    // 設定一個較長的超時時間，因為整個流程（下載、轉錄、AI分析）可能需要數分鐘
    test.setTimeout(5 * 60 * 1000); // 5 分鐘

    // --- 1. 切換到 "YouTube 轉報告" 分頁 ---
    // JULES'S FIX: The tab is a link (<a>), not a button (<button>).
    await page.getByRole('link', { name: '▶️ YouTube 轉報告' }).click();
    // JULES'S FIX: The old ID #youtube-report-tab does not exist.
    // A better way to verify navigation is to check for a unique heading on the new page.
    await expect(page.getByRole('heading', { name: 'Google API 金鑰管理' })).toBeVisible();

    // --- 2. 設定 API 金鑰和模型 ---
    await page.getByPlaceholder('在此貼上您的 Google API 金鑰').fill(USER_API_KEY);
    await page.getByRole('button', { name: '儲存金鑰' }).click();

    // 等待金鑰驗證成功並載入模型列表
    // JULES'S FIX: The success message was changed in the UI.
    await expect(page.locator('#api-key-status > span')).toHaveText('驗證成功', { timeout: 20000 });
    await expect(page.locator('#gemini-model-select')).toBeEnabled({ timeout: 10000 });

    // 選擇指定的 Gemini 模型
    // 注意：這裡我們選擇的是顯示名稱，Playwright 會自動找到對應的 <option>
    await page.locator('#gemini-model-select').selectOption({ label: TARGET_MODEL_NAME });


    // --- 3. 輸入網址 ---
    await page.getByPlaceholder('YouTube 影片網址').first().fill(YOUTUBE_URL);
    await page.getByRole('button', { name: '+ 新增一列' }).click();
    await page.getByPlaceholder('YouTube 影片網址').last().fill(BILIBILI_URL);

    // --- 4. 設定處理參數 ---
    // 勾選所有任務選項
    await page.getByLabel('重點摘要').check();
    await page.getByLabel('詳細逐字稿').check();
    await page.getByLabel('使用原文 (基於逐字稿)').check();
    await page.getByLabel('翻譯成繁體中文 (基於逐字稿)').check();

    // 選擇輸出格式為 HTML
    await page.locator('#yt-output-format-select').selectOption({ label: 'HTML 報告' });

    // --- 5. 開始處理並驗證「處理中」狀態 ---
    await page.getByRole('button', { name: '🚀 分析影片 (Gemini)' }).click();

    // 驗證按鈕進入成功建立任務的狀態
    await expect(page.getByRole('button', { name: '✅ 任務已建立' })).toBeVisible({ timeout: 10000 });

    // --- 6. 等待任務完成並驗證結果 ---
    // 在新的架構中，所有任務都在同一個列表中更新
    const tasksContainer = page.locator('#youtube-tasks');

    // 等待兩個任務項目都出現在列表中
    await expect(tasksContainer.locator('.task-item')).toHaveCount(2, { timeout: 20000 });

    // 根據標題或 URL 的一部分來定位任務，這樣更穩健
    const firstTask = tasksContainer.locator('.task-item').filter({ hasText: /mG5z-pfhIiA|Mumbling/i });
    const secondTask = tasksContainer.locator('.task-item').filter({ hasText: /xALqLQM|Bilibili/i });

    // 驗證兩個任務都可見
    await expect(firstTask).toBeVisible();
    await expect(secondTask).toBeVisible();

    // 驗證初始狀態為下載中或處理中
    await expect(firstTask.locator('.task-status-downloading, .task-status-processing, .task-status')).toBeVisible();

    // 等待第一個任務完成（出現「預覽」按鈕）
    await expect(firstTask.getByRole('link', { name: '預覽' })).toBeVisible({ timeout: 4 * 60 * 1000 });
    // 等待第二個任務完成
    await expect(secondTask.getByRole('link', { name: '預覽' })).toBeVisible({ timeout: 4 * 60 * 1000 });

    // --- 7. 驗證報告 UI 元素與功能 ---
    // 在新架構中，只有「預覽」按鈕
    await expect(firstTask.getByRole('link', { name: '預覽' })).toBeVisible();

    // 測試「預覽」彈窗
    await firstTask.getByRole('link', { name: '預覽' }).click();
    const previewModal = page.locator('#preview-modal');
    await expect(previewModal).toBeVisible();

    // 驗證 iframe 或 pre 元素存在，表示報告正在被載入
    await expect(previewModal.locator('iframe, pre')).toBeVisible({ timeout: 10000 });

    // 驗證下載按鈕也存在於彈窗中
    await expect(previewModal.getByTestId('report-download-button')).toBeVisible();

    await previewModal.locator('#modal-close-btn').click();
    await expect(previewModal).not.toBeVisible();

    // --- 8. 產生最終截圖 ---
    await page.screenshot({ path: 'e2e_youtube_report_full_success.jpg', fullPage: true });

    // 最終斷言：兩個任務都已完成（沒有處理中狀態的元素）
    await expect(tasksContainer.locator('.task-status')).toHaveCount(0, { timeout: 10000 });
  });

});
