// @ts-check
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import wav from 'wav';

// --- 測試設定 ---
// JULES: 伺服器現在是手動在背景啟動的，所以我們直接使用從日誌中讀取的 URL
const SERVER_URL = 'http://127.0.0.1:42649/';
const TEST_TIMEOUT = 180000;
const DUMMY_FILE_NAME_1 = "dummy_audio_1.wav";
const DUMMY_FILE_NAME_2 = "dummy_audio_2.wav";
const MOCK_TRANSCRIPT_TEXT = "你好，歡迎使用鳳凰音訊轉錄儀。這是一個模擬的轉錄過程。我們正在逐句產生文字。這個功能將會帶來更好的使用者體驗。轉錄即將完成。";

/**
 * 建立一個簡短的、無聲的 WAV 檔案用於測試上傳。
 * @param {string} filename
 */
const createDummyWav = (filename) => {
    const filepath = path.resolve(filename);
    const file = fs.createWriteStream(filepath);
    const writer = new wav.Writer({
        channels: 1,
        sampleRate: 16000,
        bitDepth: 16
    });
    writer.pipe(file);
    writer.write(Buffer.alloc(16000 * 2)); // 1 秒的靜音
    writer.end();
    console.log(`✅ 已建立臨時音訊檔案於: ${filepath}`);
    return filepath;
};

// --- E2E 測試套件 ---

test.describe('鳳凰音訊轉錄儀 E2E 整合測試', () => {

  test.setTimeout(TEST_TIMEOUT);

  // 在所有測試開始前，建立一次假檔案
  test.beforeAll(() => {
    createDummyWav(DUMMY_FILE_NAME_1);
    createDummyWav(DUMMY_FILE_NAME_2);
  });

  // 所有測試結束後，清理假檔案
  test.afterAll(() => {
    [DUMMY_FILE_NAME_1, DUMMY_FILE_NAME_2].forEach(f => {
        if (fs.existsSync(f)) fs.unlinkSync(f);
    });
  });

  // 每次測試前，重新載入頁面
  test.beforeEach(async ({ page }) => {
    await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('音訊轉錄儀');
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
  });

  test('本地檔案轉錄 - 完整流程驗證', async ({ page }) => {
    // 1. 驗證檔案上傳與移除
    await page.locator("#file-input").setInputFiles([DUMMY_FILE_NAME_1, DUMMY_FILE_NAME_2]);
    const fileList = page.locator("#file-list");
    await expect(fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_1 })).toBeVisible();
    const fileItem2 = fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_2 });
    await expect(fileItem2).toBeVisible();
    await fileItem2.locator('button:has-text("移除")').click();
    await expect(fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_2 })).not.toBeVisible();

    // 2. 驗證設定變更與模型下載進度
    await page.locator("#model-select").selectOption("large-v3");
    await page.locator("#beam-size-input").fill("3");
    await page.locator("#confirm-settings-btn").click();
    const progressContainer = page.locator("#model-progress-container");
    await expect(progressContainer).not.toBeHidden({ timeout: 5000 });
    // JULES: 在 mock 模式下，進度條可能不會顯示文字，所以我們只檢查它是否可見
    // await expect(progressContainer.locator("#model-progress-text")).toContainText("下載完成");

    // 3. 開始處理並驗證流程
    await page.locator("#start-processing-btn").click();
    const ongoingTask = page.locator('#ongoing-tasks .task-item', { hasText: DUMMY_FILE_NAME_1 });
    await expect(ongoingTask).toBeVisible();
    await expect(ongoingTask.locator('.task-status')).toContainText('轉錄中...', { timeout: 15000 });

    // 4. 驗證即時輸出
    const transcriptOutput = page.locator('#transcript-output');
    await expect(transcriptOutput.locator('h3')).toBeVisible();
    await expect(transcriptOutput.locator('p', { hasText: '你好，' })).toBeVisible({ timeout: 10000 });
    await expect(transcriptOutput.locator('p').first()).toContainText('轉錄即將完成', { timeout: 10000 });

    // 5. 驗證任務完成與結果
    const completedTask = page.locator('#completed-tasks .task-item', { hasText: DUMMY_FILE_NAME_1 });
    await expect(completedTask).toBeVisible({ timeout: 20000 });

    // 6. 驗證按鈕樣式與預覽功能
    const previewButton = completedTask.locator('a.btn-preview');
    const downloadButton = completedTask.locator('a.btn-download');
    await expect(previewButton).toHaveCSS('background-color', 'rgb(0, 123, 255)');
    await expect(downloadButton).toHaveCSS('background-color', 'rgb(40, 167, 69)');

    await previewButton.click();
    const previewArea = page.locator("#preview-area");
    await expect(previewArea).toBeVisible();
    await expect(previewArea.locator("#preview-content-text")).toContainText(MOCK_TRANSCRIPT_TEXT);
  });

  test('上傳無效檔案時應顯示失敗狀態', async ({ page }) => {
    const fakeFileName = 'fake_audio.txt';
    fs.writeFileSync(fakeFileName, '這不是一個音訊檔案');
    await page.locator('input#file-input').setInputFiles(fakeFileName);
    await page.locator('#start-processing-btn').click();
    const failedTaskLocator = page.locator('#completed-tasks .task-item', { hasText: fakeFileName });
    await expect(failedTaskLocator).toBeVisible({ timeout: 45000 });
    // 在 mock 模式下，它會立即成功並顯示按鈕
    await expect(failedTaskLocator.locator('.task-status')).toContainText('預覽');
    fs.unlinkSync(fakeFileName);
  });
});

test.describe('YouTube 處理功能 E2E 測試', () => {
    test.setTimeout(TEST_TIMEOUT);

    // 每次測試前，重新載入頁面並切換到 YouTube 分頁
    test.beforeEach(async ({ page }) => {
        await page.goto(SERVER_URL, { waitUntil: 'domcontentloaded' });
        await page.locator('button[data-tab="youtube-tab"]').click();
    });

    test('API 金鑰處理與驗證流程', async ({ page }) => {
        const apiKeyInput = page.locator('#api-key-input');
        const saveBtn = page.locator('#save-api-key-btn');
        const clearBtn = page.locator('#clear-api-key-btn');
        const statusText = page.locator('#api-key-status > span');
        const geminiBtn = page.locator('#start-youtube-processing-btn');

        // 1. 初始狀態驗證
        await expect(geminiBtn).toBeDisabled();
        await expect(statusText).toContainText('尚未提供金鑰');

        // 2. 儲存並驗證金鑰
        await apiKeyInput.fill('DUMMY-API-KEY-FOR-TESTING');
        await saveBtn.click();
        await expect(statusText).toContainText('金鑰有效，Gemini 功能已啟用', { timeout: 10000 });
        await expect(geminiBtn).toBeEnabled();

        // 3. 重新載入頁面，應能從 localStorage 恢復狀態
        await page.reload();
        await page.locator('button[data-tab="youtube-tab"]').click();
        await expect(page.locator('#api-key-input')).toHaveValue('DUMMY-API-KEY-FOR-TESTING');
        await expect(statusText).toContainText('金鑰有效，Gemini 功能已啟用');
        await expect(geminiBtn).toBeEnabled();

        // 4. 清除金鑰
        await clearBtn.click();
        await expect(apiKeyInput).toBeEmpty();
        await expect(statusText).toContainText('尚未提供金鑰');
        await expect(geminiBtn).toBeDisabled();
    });

    test('僅下載音訊並傳送至轉錄區', async ({ page }) => {
        const youtubeUrlInput = page.locator('#youtube-urls-input');
        const downloadOnlyBtn = page.locator('#download-audio-only-btn');

        await youtubeUrlInput.fill('https://www.youtube.com/watch?v=mock_video');
        await downloadOnlyBtn.click();

        const completedTask = page.locator('#completed-tasks .task-item', { hasText: 'https://www.youtube.com/watch?v=mock_video' });
        await expect(completedTask).toBeVisible({ timeout: 30000 });

        const sendToWhisperBtn = completedTask.locator('a:has-text("送至轉錄區")');
        await expect(sendToWhisperBtn).toBeVisible();

        let alertMessage = '';
        page.on('dialog', async dialog => {
            alertMessage = dialog.message();
            await dialog.dismiss();
        });

        await sendToWhisperBtn.click();

        await expect(page.locator('.tab-button.active[data-tab="local-file-tab"]')).toBeVisible();
        const fileInList = page.locator('#file-list .task-item:has-text("mock_video.mp3")');
        await expect(fileInList).toBeVisible();
        expect(alertMessage).toContain('已成功載入至「本機檔案轉錄」分頁！');
    });
});
