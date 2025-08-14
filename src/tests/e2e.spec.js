// @ts-check
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import wav from 'wav';

// --- 測試設定 ---
// JULES'S FIX: Remove hardcoded URL
// const SERVER_URL = 'http://127.0.0.1:42649/';
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

  test.beforeAll(() => {
    createDummyWav(DUMMY_FILE_NAME_1);
    createDummyWav(DUMMY_FILE_NAME_2);
  });

  test.afterAll(() => {
    [DUMMY_FILE_NAME_1, DUMMY_FILE_NAME_2].forEach(f => {
        if (fs.existsSync(f)) fs.unlinkSync(f);
    });
  });

  test.beforeEach(async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('音訊轉錄儀');
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 15000 });
  });

  test('本地檔案轉錄 - 完整流程驗證', async ({ page }) => {
    await page.locator("#file-input").setInputFiles([DUMMY_FILE_NAME_1, DUMMY_FILE_NAME_2]);
    const fileList = page.locator("#file-list");
    await expect(fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_1 })).toBeVisible();
    const fileItem2 = fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_2 });
    await expect(fileItem2).toBeVisible();
    await fileItem2.locator('button:has-text("移除")').click();
    await expect(fileList.locator(".task-item", { hasText: DUMMY_FILE_NAME_2 })).not.toBeVisible();

    await page.locator("#model-select").selectOption("large-v3");
    await page.locator("#beam-size-input").fill("3");
    await page.locator("#confirm-settings-btn").click();
    const progressContainer = page.locator("#model-progress-container");
    await expect(progressContainer).not.toBeHidden({ timeout: 5000 });

    await page.locator("#start-processing-btn").click();
    const ongoingTask = page.locator('#ongoing-tasks .task-item', { hasText: DUMMY_FILE_NAME_1 });
    await expect(ongoingTask).toBeVisible();
    await expect(ongoingTask.locator('.task-status')).toContainText('轉錄中...', { timeout: 15000 });

    const transcriptOutput = page.locator('#transcript-output');
    await expect(transcriptOutput.locator('h3')).toBeVisible();
    await expect(transcriptOutput).toContainText('你好', { timeout: 10000 });

    const completedTask = page.locator('#completed-tasks .task-item', { hasText: DUMMY_FILE_NAME_1 });
    await expect(completedTask).toBeVisible({ timeout: 20000 });

    const previewButton = completedTask.locator('a.btn-preview');
    await expect(previewButton).toBeVisible();
    await previewButton.click();

    const previewModal = page.locator("#preview-modal");
    await expect(previewModal).toBeVisible();

    const iframe = page.frameLocator('#preview-modal iframe#modal-iframe');
    await expect(iframe.locator('pre')).toContainText(MOCK_TRANSCRIPT_TEXT, { timeout: 10000 });

    await previewModal.locator('#modal-close-btn').click();
    await expect(previewModal).not.toBeVisible();
  });

  test('上傳無效檔案時應顯示失敗狀態', async ({ page }) => {
    const fakeFileName = 'fake_audio.txt';
    fs.writeFileSync(fakeFileName, '這不是一個音訊檔案');
    await page.locator('input#file-input').setInputFiles(fakeFileName);
    await page.locator('#start-processing-btn').click();
    const failedTaskLocator = page.locator('#completed-tasks .task-item', { hasText: fakeFileName });
    await expect(failedTaskLocator).toBeVisible({ timeout: 45000 });
    await expect(failedTaskLocator.locator('.task-status')).toContainText('預覽');
    fs.unlinkSync(fakeFileName);
  });
});

test.describe('YouTube 處理功能 E2E 測試', () => {
    test.setTimeout(TEST_TIMEOUT);

    test.beforeEach(async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded' });
        await page.locator('button[data-tab="youtube-report-tab"]').click();
    });

    test('API 金鑰處理與驗證流程', async ({ page }) => {
        const apiKeyInput = page.locator('#api-key-input');
        const saveBtn = page.locator('#save-api-key-btn');
        const clearBtn = page.locator('#clear-api-key-btn');
        const statusText = page.locator('#api-key-status > span');
        const geminiBtn = page.locator('#start-youtube-processing-btn');

        await expect(geminiBtn).toBeDisabled();
        await expect(statusText).toContainText('尚未提供金鑰');

        await apiKeyInput.fill('DUMMY-API-KEY-FOR-TESTING');
        await saveBtn.click();
        await expect(statusText).toContainText('金鑰有效，Gemini 功能已啟用', { timeout: 10000 });
        await expect(geminiBtn).toBeEnabled();

        await page.reload();
        await page.locator('button[data-tab="youtube-report-tab"]').click();
        await expect(page.locator('#api-key-input')).toHaveValue('DUMMY-API-KEY-FOR-TESTING');
        await expect(statusText).toContainText('金鑰有效，Gemini 功能已啟用');
        await expect(geminiBtn).toBeEnabled();

        await clearBtn.click();
        await expect(apiKeyInput).toBeEmpty();
        await expect(statusText).toContainText('尚未提供金鑰');
        await expect(geminiBtn).toBeDisabled();
    });

    test('僅下載音訊並傳送至轉錄區', async ({ page }) => {
        const youtubeUrlInput = page.locator('.youtube-url-input').first();
        const downloadOnlyBtn = page.locator('#download-audio-only-btn');

        await youtubeUrlInput.fill('https://www.youtube.com/watch?v=mock_video');
        await downloadOnlyBtn.click();

        const completedTask = page.locator('#completed-tasks .task-item', { hasText: 'mock_video' });
        await expect(completedTask).toBeVisible({ timeout: 30000 });

        const sendToWhisperBtn = completedTask.locator('a:has-text("送至轉錄區")');
        await expect(sendToWhisperBtn).toBeVisible();

        await sendToWhisperBtn.click();

        const statusMessage = page.locator('#status-message-text');
        await expect(statusMessage).toContainText('已成功載入至「本機檔案轉錄」分頁！', { timeout: 10000 });
    });
});
