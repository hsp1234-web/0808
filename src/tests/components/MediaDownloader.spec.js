import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * MediaDownloader 元件測試套件
 */
test.describe('MediaDownloader Component Tests', () => {

    let componentCode;
    const baseURL = `http://127.0.0.1:${process.env.PORT || 42649}`;

    test.beforeAll(() => {
        componentCode = fs.readFileSync(path.resolve('src/frontend/components/MediaDownloader.js'), 'utf-8');
    });

    /**
     * 輔助函式：在頁面中設定並初始化元件
     */
    async function setupComponent(page) {
        await page.setContent(`
            <base href="${baseURL}">
            <style>.hidden { display: none; }</style>
            <div id="downloader-container"></div>
        `);
        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { MediaDownloader } = await import(dataUrl);
            const container = document.getElementById('downloader-container');
            const services = {
                showStatusMessage: (msg) => console.log(msg),
                socket: { readyState: 1, send: () => {} },
                logAction: () => {},
                createNewTaskElement: () => console.log('createNewTaskElement called'),
            };
            const downloader = new MediaDownloader(container, services);
            downloader.init();
            window.downloader = downloader;
        }, componentCode);
    }

    // 測試案例 1: 初始渲染與選項切換
    test('should render correctly and switch options', async ({ page }) => {
        await setupComponent(page);

        // 驗證初始狀態
        await expect(page.locator('h2:has-text("媒體下載器")')).toBeVisible();
        await expect(page.locator('input[name="download-type"][value="audio"]')).toBeChecked();
        await expect(page.locator('#audio-options')).toBeVisible();
        await expect(page.locator('#video-options')).toBeHidden();
        await expect(page.locator('#remove-silence-checkbox')).toBeEnabled();

        // 切換到影片
        await page.locator('input[name="download-type"][value="video"]').check();

        // 驗證狀態變更
        await expect(page.locator('#audio-options')).toBeHidden();
        await expect(page.locator('#video-options')).toBeVisible();
        await expect(page.locator('#remove-silence-checkbox')).toBeDisabled();
    });

    // 測試案例 2: 開始下載應觸發 API 呼叫
    test('should trigger API call on start download', async ({ page }) => {
        let apiCalled = false;
        let requestPayload;

        await page.route(`${baseURL}/api/youtube/process`, async (route) => {
            apiCalled = true;
            requestPayload = route.request().postDataJSON();
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ success: true, tasks: [{ task_id: 'download-123' }] })
            });
        });

        await setupComponent(page);

        // 輸入 URL 並點擊下載
        const testUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
        await page.locator('#downloader-urls-input').fill(testUrl);

        // 使用 Promise.all 來同時觸發點擊並等待回應
        await Promise.all([
            page.waitForResponse(resp => resp.url().includes('/api/youtube/process')),
            page.locator('#start-download-btn').click()
        ]);

        // 驗證 API 呼叫和 payload
        expect(apiCalled).toBe(true);
        expect(requestPayload.requests[0].url).toBe(testUrl);
        expect(requestPayload.download_only).toBe(true);
        expect(requestPayload.download_type).toBe('audio');

        // 驗證輸入框是否被清空
        await expect(page.locator('#downloader-urls-input')).toHaveValue('');
    });

    // 測試案例 3: 上傳 Cookies 應觸發 API 呼叫
    test('should trigger API call on cookies upload', async ({ page }) => {
        let apiCalled = false;

        await page.route(`${baseURL}/api/upload_cookies`, async (route) => {
            apiCalled = true;
            // 簡單驗證請求已發送
            expect(route.request().method()).toBe('POST');
            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ message: 'Cookies uploaded successfully' })
            });
        });

        await setupComponent(page);

        const fileChooserPromise = page.waitForEvent('filechooser');
        await page.locator('#upload-cookies-btn').click();
        const fileChooser = await fileChooserPromise;
        await fileChooser.setFiles({
            name: 'cookies.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from('youtube cookies content')
        });

        // 等待 API 回應
        await page.waitForResponse(resp => resp.url().includes('/api/upload_cookies'));

        // 驗證 API 是否被呼叫
        expect(apiCalled).toBe(true);
    });
});
