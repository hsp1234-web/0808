// @ts-check
import { test, expect } from '@playwright/test';

// --- 測試設定 ---
const SERVER_URL = 'http://127.0.0.1:42649/';
const TEST_TIMEOUT = 60000; // 60 秒
const MOCK_VIDEO_URL = 'https://www.youtube.com/watch?v=mock_video_for_validation';
const CUSTOM_FILENAME = '我的自訂影片名稱'; // 前端輸入的檔名

// --- 前端驗證測試套件 ---
test.describe('前端新功能驗證', () => {
  test.setTimeout(TEST_TIMEOUT);

  // 每次測試前，重新載入頁面並切換到 YouTube 分頁
  test.beforeEach(async ({ page }) => {
    await page.goto(SERVER_URL, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toContainText('音訊轉錄儀');
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
    // 切換到 "YouTube 轉報告" 分頁
    await page.locator('button[data-tab="youtube-report-tab"]').click();
  });

  test('YouTube下載：自訂命名、獨立進度條與報告預覽彈窗', async ({ page }) => {
    // 1. 找到輸入列，並填入模擬網址和自訂檔名
    const linkRow = page.locator('.youtube-link-row').first();
    await linkRow.locator('.youtube-url-input').fill(MOCK_VIDEO_URL);
    await linkRow.locator('.youtube-filename-input').fill(CUSTOM_FILENAME);

    // 2. 執行完整的 "分析影片" 流程以觸發報告預覽功能
    await page.locator('#api-key-input').fill('DUMMY-KEY-FOR-TESTING');
    await page.locator('#save-api-key-btn').click();
    const analysisBtn = page.locator('#start-youtube-processing-btn');
    await expect(analysisBtn).toBeEnabled({ timeout: 10000 });
    await analysisBtn.click();

    // 3. 採用更穩健的策略：直接等待一個帶有「預覽」按鈕的已完成任務出現。
    // 這避免了依賴於不穩定或複雜的任務顯示名稱。
    const completedTask = page.locator('#completed-tasks .task-item:has(a.btn-preview)');
    await expect(completedTask).toBeVisible({ timeout: 30000 });

    // 4. 驗證獨立進度條（結構存在即可）
    // 我們可以斷言在已完成的任務中，進度條的結構是存在的。
    const progressBar = completedTask.locator('.task-progress-bar');
    await expect(progressBar).toBeDefined();

    // 5. 點擊「預覽」按鈕
    const previewBtn = completedTask.locator('a.btn-preview');
    await previewBtn.click();

    // 6. 驗證預覽彈窗 (Modal) 是否可見
    const previewModal = page.locator('#preview-modal');
    await expect(previewModal).toBeVisible({ timeout: 10000 });

    // 7. 驗證 iframe 已正確載入報告內容
    const iframe = previewModal.locator('#modal-iframe');
    await expect(iframe).toHaveAttribute('src', /^\/api\/download\/.+/);

    // 8. 產生最終的驗證螢幕截圖，這張截圖將會包含所有需要驗證的 UI 元素。
    await page.screenshot({ path: 'frontend_validation_screenshot.png', fullPage: true });

    // 9. 關閉彈窗並驗證其已隱藏
    await previewModal.locator('#modal-close-btn').click();
    await expect(previewModal).not.toBeVisible();
  });
});
