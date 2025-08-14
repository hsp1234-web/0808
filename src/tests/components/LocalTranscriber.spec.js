import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * LocalTranscriber 元件測試套件
 */
test.describe('LocalTranscriber Component Tests', () => {

    let componentCode;
    const baseURL = `http://127.0.0.1:${process.env.PORT || 42649}`;

    // 在所有測試執行前，讀取一次元件的原始碼
    test.beforeAll(() => {
        componentCode = fs.readFileSync(path.resolve('src/frontend/components/LocalTranscriber.js'), 'utf-8');
    });

    // 測試案例 1: 初始渲染是否正確
    test('should render correctly with initial state', async ({ page }) => {
        // 載入一個空的 HTML 頁面並設定 base URL
        await page.setContent(`<base href="${baseURL}"><div id="transcriber-container"></div>`);

        // 在頁面中注入並初始化元件
        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { LocalTranscriber } = await import(dataUrl);
            const container = document.getElementById('transcriber-container');
            // 模擬傳入的 services
            const services = {
                showStatusMessage: () => {},
                socket: { readyState: 1, send: () => {} },
                logAction: () => {},
                updateModelDisplay: () => {},
            };
            const transcriber = new LocalTranscriber(container, services);
            transcriber.init();
            window.transcriber = transcriber;
        }, componentCode);

        // 驗證 UI 元素的初始狀態
        await expect(page.locator('h2:has-text("步驟 1: 選項")')).toBeVisible();
        await expect(page.locator('h2:has-text("步驟 2: 上傳檔案")')).toBeVisible();
        await expect(page.locator('#model-select')).toHaveValue('tiny');
        await expect(page.locator('#language-select')).toHaveValue('zh');
        await expect(page.locator('#file-list')).toContainText('尚未選擇任何檔案');
        await expect(page.locator('#start-processing-btn')).toBeDisabled();
        await expect(page.locator('#model-progress-container')).toBeHidden();
    });

    // 測試案例 2: 檔案選擇與移除功能
    test('should handle file selection and removal', async ({ page }) => {
        await page.setContent(`<base href="${baseURL}"><div id="transcriber-container"></div>`);
        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { LocalTranscriber } = await import(dataUrl);
            const container = document.getElementById('transcriber-container');
            const services = { showStatusMessage: () => {}, socket: { readyState: 1, send: () => {} }, logAction: () => {}, updateModelDisplay: () => {} };
            const transcriber = new LocalTranscriber(container, services);
            transcriber.init();
            window.transcriber = transcriber;
        }, componentCode);

        // 模擬檔案選擇
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles([
            { name: 'test1.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('file1') },
            { name: 'test2.wav', mimeType: 'audio/wav', buffer: Buffer.from('file2') }
        ]);

        // 驗證檔案列表已更新
        await expect(page.locator('#file-list')).toContainText('test1.mp3');
        await expect(page.locator('#file-list')).toContainText('test2.wav');
        await expect(page.locator('#start-processing-btn')).toBeEnabled();
        await expect(page.locator('#start-processing-btn')).toContainText('開始處理 2 個檔案');

        // 模擬移除一個檔案
        await page.locator('.remove-file-btn[data-index="0"]').click();
        await expect(page.locator('#file-list')).not.toContainText('test1.mp3');
        await expect(page.locator('#file-list')).toContainText('test2.wav');
        await expect(page.locator('#start-processing-btn')).toContainText('開始處理 1 個檔案');

        // 模擬移除最後一個檔案
        await page.locator('.remove-file-btn[data-index="0"]').click();
        await expect(page.locator('#file-list')).toContainText('尚未選擇任何檔案');
        await expect(page.locator('#start-processing-btn')).toBeDisabled();
    });

    // 測試案例 3: 點擊開始處理按鈕應觸發 API 呼叫
    test('should trigger API call on start processing click', async ({ page }) => {
        // 攔截 /api/transcribe 請求
        let apiCallCount = 0;
        await page.route(`${baseURL}/api/transcribe`, async (route) => {
            apiCallCount++;
            // FormData 的驗證比較複雜，我們在這裡只驗證請求被發送，
            // 並回傳一個成功的假回應來觸發後續邏輯。
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true, tasks: [{ type: 'transcribe', task_id: 'task-123' }] })
            });
        });

        await page.setContent(`<base href="${baseURL}"><div id="transcriber-container"></div>`);
        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { LocalTranscriber } = await import(dataUrl);
            const container = document.getElementById('transcriber-container');
            const services = { showStatusMessage: () => {}, socket: { readyState: 1, send: () => {} }, logAction: () => {}, updateModelDisplay: () => {} };
            const transcriber = new LocalTranscriber(container, services);
            transcriber.init();
            window.transcriber = transcriber;
        }, componentCode);

        // 選擇檔案
        await page.locator('input[type="file"]').setInputFiles({ name: 'test.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('a file') });

        // 點擊按鈕，並等待 API 回應
        await Promise.all([
            page.waitForResponse(response => response.url().includes('/api/transcribe') && response.status() === 200),
            page.locator('#start-processing-btn').click()
        ]);

        // 驗證 API 是否被呼叫
        expect(apiCallCount).toBe(1);

        // 驗證 UI 是否被重置
        await expect(page.locator('#file-list')).toContainText('尚未選擇任何檔案');
        await expect(page.locator('#start-processing-btn')).toBeDisabled();
    });

    // 測試案例 4: 模型下載進度條應正確顯示
    test('should display model download progress correctly', async ({ page }) => {
        await page.setContent(`<base href="${baseURL}"><div id="transcriber-container"></div>`);
        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { LocalTranscriber } = await import(dataUrl);
            const container = document.getElementById('transcriber-container');
            const services = { showStatusMessage: () => {}, socket: { readyState: 1, send: () => {} }, logAction: () => {}, updateModelDisplay: () => {} };
            const transcriber = new LocalTranscriber(container, services);
            transcriber.init();
            window.transcriber = transcriber;
        }, componentCode);

        // 模擬下載中
        await page.evaluate(() => {
            window.transcriber.handleModelDownloadStatus({ status: 'downloading', description: 'data.bin', percent: 50 });
        });
        await expect(page.locator('#model-progress-container')).toBeVisible();
        await expect(page.locator('#model-progress-text')).toContainText('下載中');
        await expect(page.locator('#model-progress-bar')).toHaveAttribute('style', 'width: 50%; background-color: var(--button-bg-color);');

        // 模擬下載完成
        await page.evaluate(() => {
            window.transcriber.handleModelDownloadStatus({ status: 'completed' });
        });
        await expect(page.locator('#model-progress-text')).toContainText('下載完成');
        await expect(page.locator('#model-progress-bar')).toHaveAttribute('style', 'width: 100%; background-color: var(--button-bg-color);');

        // 模擬下載失敗
        await page.evaluate(() => {
            window.transcriber.handleModelDownloadStatus({ status: 'failed', error: 'Checksum mismatch' });
        });
        await expect(page.locator('#model-progress-text')).toContainText('下載失敗: Checksum mismatch');
        await expect(page.locator('#model-progress-bar')).toHaveAttribute('style', 'width: 100%; background-color: rgb(220, 53, 69);');
    });
});
