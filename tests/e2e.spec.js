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
        serverUrl = `${APP_URL_BASE}:${apiPort}/static/mp3.html`;
        clearTimeout(timeout);
        resolve(serverUrl);
        return;
      }
    } catch (error) {
      // 預期會收到連線被拒的錯誤，直到伺服器就緒
      if (error.cause && error.cause.code === 'ECONNREFUSED') {
        // 正常，繼續輪詢
      } else {
        console.warn(`健康檢查時發生非預期錯誤: ${error.message}`);
      }
    }
    // 繼續下一次輪詢
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
        // 取得埠號後，開始進行健康檢查
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


// --- E2E 測試套件 ---
test.describe('鳳凰音訊轉錄儀 E2E 測試', () => {

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

  test('應成功上傳音訊檔案並顯示完成狀態', async ({ page }) => {
    await page.goto(serverUrl);

    await expect(page.locator('#upload-container')).toBeVisible();

    const fileInput = page.locator('input[type="file"]');
    const filePath = 'dummy_audio.wav';
    await fileInput.setInputFiles(filePath);

    const completedTasksContainer = page.locator('#completed-tasks');
    const taskLocator = completedTasksContainer.locator('.p-3', { hasText: path.basename(filePath) });

    await expect(taskLocator.locator('p', { hasText: '已完成' })).toBeVisible({ timeout: 45000 });

    await expect(taskLocator.locator('.text-green-500')).toBeVisible();
  });

  test('上傳無效檔案時應顯示失敗狀態且 UI 保持穩定', async ({ page }) => {
    const fakeFileName = 'fake_audio.txt';
    fs.writeFileSync(fakeFileName, '這不是一個音訊檔案');

    await page.goto(serverUrl);

    await expect(page.locator('#upload-container')).toBeVisible();

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(fakeFileName);

    const completedTasksContainer = page.locator('#completed-tasks');
    const taskLocator = completedTasksContainer.locator('.p-3', { hasText: fakeFileName });

    await expect(taskLocator.locator('p', { hasText: '失敗' })).toBeVisible({ timeout: 45000 });

    await expect(taskLocator.locator('.text-red-500')).toBeVisible();

    await expect(page.locator('#upload-container')).toBeVisible();

    fs.unlinkSync(fakeFileName);
  });
});
