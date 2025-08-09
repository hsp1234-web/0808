// @ts-check
import { test, expect } from '@playwright/test';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

// --- 測試設定 ---
const APP_URL_BASE = 'http://127.0.0.1';
const START_SERVER_COMMAND = 'python';
const START_SERVER_ARGS = ['orchestrator.py', '--mock'];
const SERVER_READY_TIMEOUT = 60000; // 伺服器啟動的超時時間 (60秒)
const TEST_TIMEOUT = 90000; // 單一測試案例的超時時間 (90秒)
const HEALTH_CHECK_POLL_INTERVAL = 500; // 健康檢查輪詢間隔 (毫秒)

// --- 輔助函式與狀態變數 ---
let serverProcess;
let serverUrl;
let apiPort;
let serverLogs = '';

/**
 * 啟動後端伺服器並等待其就緒。
 * @returns {Promise<string>} 就緒後前端頁面的 URL。
 */
const startServer = () => new Promise((resolve, reject) => {
  console.log(`🚀 正在啟動伺服器: ${START_SERVER_COMMAND} ${START_SERVER_ARGS.join(' ')}`);
  serverProcess = spawn(START_SERVER_COMMAND, START_SERVER_ARGS, {
    stdio: ['pipe', 'pipe', 'pipe'],
    encoding: 'utf-8'
  });

  const timeout = setTimeout(() => {
    console.error('❌ 伺服器啟動超時。');
    console.error('--- 伺服器日誌 ---');
    console.error(serverLogs);
    reject(new Error('伺服器啟動超時。'));
    killServer();
  }, SERVER_READY_TIMEOUT);

  // 健康檢查輪詢函式
  const pollHealthCheck = async () => {
    const healthUrl = `${APP_URL_BASE}:${apiPort}/api/health`;
    try {
      const response = await fetch(healthUrl);
      if (response.ok) {
        console.log('✅ 健康檢查成功，API 伺服器已就緒！');
        // V3 UI 的 HTML 檔案路徑是 /，由 FastAPI 在根目錄提供
        serverUrl = `${APP_URL_BASE}:${apiPort}/`;
        clearTimeout(timeout);
        resolve(serverUrl);
        return;
      }
    } catch (error) {
      if (error.cause && error.cause.code === 'ECONNREFUSED') {
        // 正常，繼續輪詢
      } else {
        console.warn(`健康檢查時發生非預期錯誤: ${error.message}`);
      }
    }
    setTimeout(pollHealthCheck, HEALTH_CHECK_POLL_INTERVAL);
  };

  const onData = (data) => {
    const output = data.toString();
    serverLogs += output;
    // console.log(`[伺服器]: ${output.trim()}`);

    if (!apiPort) {
      const portMatch = output.match(/API_PORT:\s*(\d+)/);
      if (portMatch) {
        apiPort = portMatch[1];
        console.log(`✅ 偵測到 API 埠號: ${apiPort}`);
        pollHealthCheck();
      }
    }
  };

  serverProcess.stdout.on('data', onData);
  serverProcess.stderr.on('data', onData);

  serverProcess.on('close', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`❌ 伺服器意外終止，代碼: ${code}`);
      clearTimeout(timeout);
      reject(new Error(`伺服器進程以代碼 ${code} 退出`));
    }
  });
});

/**
 * 停止後端伺服器。
 */
const killServer = () => {
  if (serverProcess && !serverProcess.killed) {
    console.log('🛑 正在停止伺服器...');
    const killed = serverProcess.kill('SIGTERM');
    if (killed) {
        console.log('✅ 伺服器進程已終止。');
    } else {
        console.error('❌ 無法終止伺服器進程。');
    }
  }
};


// --- E2E 測試套件 (V3 UI) ---
test.describe('鳳凰音訊轉錄儀 V3 E2E 測試', () => {

  test.setTimeout(TEST_TIMEOUT);

  test.beforeAll(async () => {
    try {
      serverUrl = await startServer();
    } catch (error) {
      console.error('為測試啟動伺服器時失敗:', error);
      process.exit(1);
    }
  });

  test.afterAll(() => {
    killServer();
  });

  test('應成功上傳音訊檔案，歷經處理中，最終顯示完成狀態', async ({ page }) => {
    await page.goto(serverUrl, { waitUntil: 'domcontentloaded' });

    // 1. 確保 UI 初始狀態正確
    await expect(page.locator('h1')).toContainText('鳳凰 音訊轉錄儀 v3');
    await expect(page.locator('#ongoing-tasks')).toContainText('暫無執行中任務');
    await expect(page.locator('#completed-tasks')).toContainText('尚無完成的任務');

    // 2. 選擇檔案
    const fileInput = page.locator('input#file-input');
    const filePath = 'dummy_audio.wav';
    await fileInput.setInputFiles(filePath);

    // 3. 點擊開始處理按鈕
    const startButton = page.locator('button', { hasText: '開始處理' });
    await expect(startButton).toBeEnabled();
    await expect(startButton).toContainText('開始處理 1 個檔案');
    await startButton.click();

    // 4. 驗證任務出現在「進行中」列表
    const ongoingTasksContainer = page.locator('#ongoing-tasks');
    const ongoingTaskLocator = ongoingTasksContainer.locator('div', { hasText: path.basename(filePath) });
    await expect(ongoingTaskLocator).toBeVisible({ timeout: 10000 });
    await expect(ongoingTaskLocator).toContainText('processing...');

    // 5. 等待並驗證任務移動到「已完成」列表
    const completedTasksContainer = page.locator('#completed-tasks');
    const completedTaskLocator = completedTasksContainer.locator('div', { hasText: path.basename(filePath) });
    await expect(completedTaskLocator).toBeVisible({ timeout: 45000 });

    // 6. 驗證完成狀態的 UI
    await expect(completedTaskLocator).toContainText('已完成');
    // 檢查是否有綠色樣式 (表示成功)
    const successText = completedTaskLocator.locator('.text-green-600');
    await expect(successText).toBeVisible();

    // 7. 驗證「進行中」列表已清空
    await expect(ongoingTasksContainer).toContainText('暫無執行中任務');
  });

  test('上傳無效檔案時應顯示失敗狀態', async ({ page }) => {
    await page.goto(serverUrl, { waitUntil: 'domcontentloaded' });

    // 1. 準備無效檔案
    const fakeFileName = 'fake_audio.txt';
    fs.writeFileSync(fakeFileName, '這不是一個音訊檔案');

    // 2. 上傳並開始處理
    await page.locator('input#file-input').setInputFiles(fakeFileName);
    await page.locator('button', { hasText: '開始處理' }).click();

    // 3. 等待並驗證任務出現在「已完成」列表且狀態為「失敗」
    const completedTasksContainer = page.locator('#completed-tasks');
    const failedTaskLocator = completedTasksContainer.locator('div', { hasText: fakeFileName });
    await expect(failedTaskLocator).toBeVisible({ timeout: 45000 });

    // 4. 驗證失敗狀態的 UI
    await expect(failedTaskLocator).toContainText('失敗');
    // 檢查是否有紅色樣式
    const failureText = failedTaskLocator.locator('.text-red-600');
    await expect(failureText).toBeVisible();

    // 清理臨時檔案
    fs.unlinkSync(fakeFileName);
  });
});
