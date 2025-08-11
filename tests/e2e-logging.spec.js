// @ts-check
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// --- 測試設定 ---
// 伺服器 URL 應與 local_run.py 中啟動的伺服器一致。
// 這裡我們用一個佔位符，實際執行時 local_run.py 會提供正確的 URL。
// 我們從環境變數讀取它，如果沒有就用一個預設值。
const SERVER_URL = process.env.SERVER_URL || 'http://127.0.0.1:8000/'; // 預設值，可能需要調整
const LOG_FILE_PATH = path.resolve('run_log.txt');
const TEST_TIMEOUT = 60000; // 60 秒

/**
 * 等待日誌檔案中出現指定的字串。
 * @param {string} searchText - 要尋找的文字。
 * @param {number} timeout - 超時時間（毫秒）。
 * @returns {Promise<void>}
 */
const waitForLogContent = (searchText, timeout = 10000) => {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        const interval = setInterval(() => {
            if (Date.now() - startTime > timeout) {
                clearInterval(interval);
                reject(new Error(`等待日誌內容 "${searchText}" 超時`));
                return;
            }

            if (fs.existsSync(LOG_FILE_PATH)) {
                const content = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
                if (content.includes(searchText)) {
                    clearInterval(interval);
                    resolve();
                }
            }
        }, 300); // 每 300ms 檢查一次
    });
};


// --- E2E 測試套件 ---
test.describe('前端操作日誌 E2E 測試', () => {

  test.setTimeout(TEST_TIMEOUT);

  // 在每次測試前，清理日誌檔案並重新載入頁面
  test.beforeEach(async ({ page }) => {
    // 監聽並印出所有瀏覽器主控台訊息，以便除錯
    page.on('console', msg => {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
    });

    // 清理日誌檔案
    if (fs.existsSync(LOG_FILE_PATH)) {
        fs.unlinkSync(LOG_FILE_PATH);
    }
    // 導覽至頁面並等待 WebSocket 連線
    await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
    // 在開始測試前，等待一小段時間確保初始的 websocket-connect-success 日誌已寫入
    await waitForLogContent('websocket-connect-success');
    // 再次清理，以忽略連線成功時的日誌，專注於測試使用者互動
    fs.unlinkSync(LOG_FILE_PATH);
  });

  test('應能正確記錄各種 UI 互動', async ({ page }) => {
    // 1. 測試按鈕點擊 (Button Click)
    await test.step('測試按鈕點擊', async () => {
        await page.locator('#confirm-settings-btn').click();
        await waitForLogContent('click-confirm-settings: medium');
        const logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] click-confirm-settings: medium');
    });

    // 2. 測試分頁切換 (Tab Click)
    await test.step('測試分頁切換', async () => {
        await page.locator('button[data-tab="downloader-tab"]').click();
        await waitForLogContent('click-tab: downloader-tab');
        const logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] click-tab: downloader-tab');
    });

    // 3. 測試下拉選單變更 (Select Change)
    await test.step('測試下拉選單變更', async () => {
        // 切換回第一個分頁以顯示模型選擇
        await page.locator('button[data-tab="local-file-tab"]').click();
        await page.locator('#model-select').selectOption('large-v3');
        await waitForLogContent('change-model-select: large-v3');
        const logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] change-model-select: large-v3');
    });

    // 4. 測試核取方塊 (Checkbox Toggle)
    await test.step('測試核取方塊', async () => {
        // 切換到下載器分頁以顯示核取方塊
        await page.locator('button[data-tab="downloader-tab"]').click();
        await page.locator('#remove-silence-checkbox').check();
        await waitForLogContent('toggle-remove-silence: true');
        let logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] toggle-remove-silence: true');

        await page.locator('#remove-silence-checkbox').uncheck();
        await waitForLogContent('toggle-remove-silence: false');
        logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] toggle-remove-silence: false');
    });

    // 5. 測試日誌檢視器篩選器
    await test.step('測試日誌檢視器篩選器', async () => {
        await page.locator('input[name="log-level"][value="ERROR"]').uncheck();
        await waitForLogContent('toggle-log-level-filter: ERROR');
        const logContent = fs.readFileSync(LOG_FILE_PATH, 'utf-8');
        expect(logContent).toContain('[FRONTEND ACTION] toggle-log-level-filter: ERROR');
    });
  });
});
