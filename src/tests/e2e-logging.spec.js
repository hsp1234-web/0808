// @ts-check
import { test, expect } from '@playwright/test';

// --- 測試設定 ---
// JULES'S FIX: Remove hardcoded URL
// const SERVER_URL = process.env.SERVER_URL || 'http://127.0.0.1:42649/'; // 使用 run_for_playwright.py 的埠號
const TEST_TIMEOUT = 60000; // 60 秒

/**
 * 輪詢偵錯端點，並期望最新的日誌包含指定的訊息。
 * @param {import('@playwright/test').Page} page - Playwright Page 物件。
 * @param {string} expectedMessage - 期望日誌訊息中包含的文字。
 * @returns {Promise<void>}
 */
const expectLatestLogToContain = async (page, expectedMessage) => {
    await expect(async () => {
        const response = await page.request.get(`${SERVER_URL}api/debug/latest_frontend_action_log`);
        expect(response.ok(), `API 請求失敗: ${response.status()}`).toBeTruthy();

        const json = await response.json();
        expect(json.latest_log, 'API 回應中最新的日誌為 null').not.toBeNull();

        // 期望日誌的 message 欄位包含我們正在尋找的文字
        expect(json.latest_log.message, `最新的日誌訊息不包含 "${expectedMessage}"`).toContain(expectedMessage);

        // 順便驗證一下日誌來源是否正確
        expect(json.latest_log.source, '日誌來源不正確').toBe('frontend_action');

    }).toPass({
        // Poll every 300ms, for up to 10 seconds.
        // 輪詢配置：每 300 毫秒檢查一次，最多等待 10 秒。
        intervals: [300, 500, 1000],
        timeout: 10000
    });
};

// --- E2E 測試套件 ---
test.describe('前端操作日誌 E2E 測試 (資料庫模式)', () => {

  test.setTimeout(TEST_TIMEOUT);

  // 在每次測試前，重新載入頁面
  test.beforeEach(async ({ page }) => {
    // 監聽並印出所有瀏覽器主控台訊息，以便除錯
    page.on('console', msg => {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    // 導覽至頁面並等待 WebSocket 連線
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });

    // JULES'S FIX: Add a dummy action to flush any lingering logs from previous tests.
    // This makes the logging test independent and robust against pollution.
    await page.locator('#zoom-in-btn').click();
    await expectLatestLogToContain(page, 'click-zoom-in');
  });

  test('應能正確將各種 UI 互動記錄到資料庫', async ({ page }) => {

    // 1. 測試按鈕點擊 (Button Click)
    await test.step('測試按鈕點擊', async () => {
        await page.locator('#confirm-settings-btn').click();
        await expectLatestLogToContain(page, 'click-confirm-settings: medium');
    });

    // 2. 測試分頁切換 (Tab Click)
    await test.step('測試分頁切換', async () => {
        await page.locator('button[data-tab="downloader-tab"]').click();
        await expectLatestLogToContain(page, 'click-tab: downloader-tab');
    });

    // 3. 測試下拉選單變更 (Select Change)
    await test.step('測試下拉選單變更', async () => {
        // 切換回第一個分頁以顯示模型選擇
        await page.locator('button[data-tab="local-file-tab"]').click();
        await page.locator('#model-select').selectOption('large-v3');
        await expectLatestLogToContain(page, 'change-model-select: large-v3');
    });

    // 4. 測試核取方塊 (Checkbox Toggle)
    await test.step('測試核取方塊', async () => {
        // 切換到下載器分頁以顯示核取方塊
        await page.locator('button[data-tab="downloader-tab"]').click();

        await page.locator('#remove-silence-checkbox').check();
        await expectLatestLogToContain(page, 'toggle-remove-silence: true');

        await page.locator('#remove-silence-checkbox').uncheck();
        await expectLatestLogToContain(page, 'toggle-remove-silence: false');
    });

    // 5. 測試日誌檢視器篩選器
    await test.step('測試日誌檢視器篩選器', async () => {
        await page.locator('input[name="log-level"][value="ERROR"]').uncheck();
        await expectLatestLogToContain(page, 'toggle-log-level-filter: ERROR');
    });
  });
});
