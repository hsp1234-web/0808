// @ts-check
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const SERVER_URL = process.env.SERVER_URL || 'http://127.0.0.1:42649/';
const TEST_TIMEOUT = 60000;

// Helper to check for the status message
const expectStatusMessage = async (page, expectedMessage, isError = false) => {
    const statusMessageArea = page.locator('#status-message-area');
    await expect(statusMessageArea).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#status-message-text')).toHaveText(expectedMessage);
    if (isError) {
        await expect(statusMessageArea).toHaveCSS('background-color', 'rgb(248, 215, 218)');
    }
};

test.describe('綜合功能 E2E 測試', () => {

    test.setTimeout(TEST_TIMEOUT);

    test.beforeEach(async ({ page }) => {
        await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });
        await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
    });

    test('應能正確顯示錯誤訊息，而非彈出視窗', async ({ page }) => {
        // 切換到媒體下載器分頁
        await page.locator('button[data-tab="downloader-tab"]').click();

        // 不輸入任何網址就點擊下載
        await page.locator('#start-download-btn').click();

        // 驗證紅色錯誤訊息是否出現
        await expectStatusMessage(page, '請輸入至少一個網址。', true);
    });

    test('應能成功提交 YouTube 下載任務', async ({ page }) => {
        // 切換到媒體下載器分頁
        await page.locator('button[data-tab="downloader-tab"]').click();

        // 輸入 YouTube 網址
        const youtubeUrl = 'https://www.youtube.com/shorts/WjlzBHaaqa4';
        await page.locator('#downloader-urls-input').fill(youtubeUrl);

        // 點擊下載
        await page.locator('#start-download-btn').click();

        // 驗證下載佇列中是否出現新任務
        const taskList = page.locator('#downloader-tasks');
        await expect(taskList.locator('.task-item')).toHaveCount(1, { timeout: 10000 });
        const taskText = await taskList.locator('.task-item .task-filename').textContent();
        expect(taskText).toContain(youtubeUrl);
    });

    test('應能使用 Base64 成功上傳本地檔案', async ({ page }) => {
        // 讀取 dummy audio 檔案並轉為 Base64
        const audioFilePath = path.resolve('dummy_audio.wav');
        const audioFileBuffer = fs.readFileSync(audioFilePath);
        const audioBase64 = audioFileBuffer.toString('base64');

        // 使用 page.evaluate 在瀏覽器中執行 JS 來處理 Base64
        await page.evaluate(async (base64) => {
            // 將 Base64 轉回 ArrayBuffer
            const byteCharacters = atob(base64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'audio/wav' });

            // 建立 File 物件
            const file = new File([blob], 'dummy_audio.wav', { type: 'audio/wav' });

            // 建立 DataTransfer 物件，這是模擬拖放所必需的
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);

            // 找到放置區並觸發 drop 事件
            const dropZone = document.querySelector('.file-drop-zone');
            if (dropZone) {
                const dropEvent = new DragEvent('drop', {
                    bubbles: true,
                    cancelable: true,
                    dataTransfer: dataTransfer,
                });
                dropZone.dispatchEvent(dropEvent);
            }
        }, audioBase64);

        // 驗證檔案是否出現在待上傳列表
        await expect(page.locator('#file-list .task-item')).toHaveCount(1);
        await expect(page.locator('#file-list .task-filename')).toHaveText('dummy_audio.wav');

        // 點擊開始處理按鈕
        await page.locator('#start-processing-btn').click();

        // 驗證進行中任務列表是否出現新任務
        const ongoingTasks = page.locator('#ongoing-tasks');
        await expect(ongoingTasks.locator('.task-item')).toHaveCount(1, { timeout: 10000 });
        const taskText = await ongoingTasks.locator('.task-item .task-filename').textContent();
        expect(taskText).toContain('dummy_audio.wav');
    });
});
