// @ts-check
import { test, expect } from '@playwright/test';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

// --- 測試設定 ---
const APP_URL_BASE = 'http://127.0.0.1';
const START_SERVER_COMMAND = 'python';
const START_SERVER_ARGS = ['orchestrator.py', '--no-worker']; // 使用模擬模式且不啟動 worker
const SERVER_READY_TIMEOUT = 60000; // 伺服器啟動的超時時間 (60秒)
const TEST_TIMEOUT = 180000; // 延長超時時間以應對模型下載 (180秒)
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

  // 測試現在應該會快很多，但我們保留較長的超時以應對 CI 環境中的波動
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

  test('應成功上傳音訊檔案並透過 WebSocket 看到即時更新', async ({ page }) => {
    await page.goto(serverUrl, { waitUntil: 'domcontentloaded' });

    // 1. 確保 UI 初始狀態正確
    await expect(page.locator('h1')).toContainText('鳳凰音訊轉錄儀 v3');
    // 等待 WebSocket 連線成功
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 10000 });

    // 2. 選擇檔案
    const fileInput = page.locator('input#file-input');
    const filePath = 'dummy_audio.wav';
    const fileName = path.basename(filePath);
    await fileInput.setInputFiles(filePath);
    await expect(page.locator('#start-processing-btn')).toBeEnabled();

    // 3. 點擊開始處理按鈕
    await page.locator('#start-processing-btn').click();

    // 4. 驗證上傳流程
    // 任務出現在「進行中」列表
    const ongoingTasksContainer = page.locator('#ongoing-tasks');
    const taskLocator = ongoingTasksContainer.locator('.task-item', { hasText: fileName });
    await expect(taskLocator).toBeVisible();

    // 上傳進度條正常顯示並消失
    const uploadProgressContainer = page.locator('#upload-progress-container');
    await expect(uploadProgressContainer).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#upload-progress-text')).toContainText(/正在上傳.*100%/);
    await expect(uploadProgressContainer).toBeHidden({ timeout: 10000 });

    // 狀態變為「已發送轉錄請求...」
    await expect(taskLocator.locator('.task-status')).toContainText('已發送轉錄請求...', { timeout: 5000 });

    // 5. 驗證 WebSocket 即時回饋
    // 狀態變為「轉錄中...」
    await expect(taskLocator.locator('.task-status')).toContainText('轉錄中...', { timeout: 15000 });

    // 即時輸出區塊出現標題和串流內容
    const transcriptOutput = page.locator('#transcript-output');
    await expect(transcriptOutput.locator('h3')).toHaveText(fileName);

    // 驗證模擬的串流文字是否逐步出現
    await expect(page.locator('p', { hasText: '你好，' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('p', { hasText: '轉錄即將完成。' })).toBeVisible({ timeout: 10000 });

    // 6. 驗證任務完成
    // 任務移至「已完成」列表
    const completedTasksContainer = page.locator('#completed-tasks');
    const completedTaskLocator = completedTasksContainer.locator('.task-item', { hasText: fileName });
    await expect(completedTaskLocator).toBeVisible({ timeout: 30000 });

    // 狀態顯示為「完成」
    await expect(completedTaskLocator.locator('.task-status')).toContainText('✅ 完成');
  });

  test('上傳無效檔案時應顯示失敗狀態', async ({ page }) => {
    await page.goto(serverUrl, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('#status-text')).toContainText('已連線', { timeout: 10000 });

    // 1. 準備無效檔案
    const fakeFileName = 'fake_audio.txt';
    fs.writeFileSync(fakeFileName, '這不是一個音訊檔案');

    // 2. 上傳並開始處理
    await page.locator('input#file-input').setInputFiles(fakeFileName);
    await page.locator('#start-processing-btn').click();

    // 3. 等待並驗證任務出現在「已完成」列表且狀態為「失敗」
    const completedTasksContainer = page.locator('#completed-tasks');
    const failedTaskLocator = completedTasksContainer.locator('.task-item', { hasText: fakeFileName });

    // 等待任務轉移到「已完成」區塊
    await expect(failedTaskLocator).toBeVisible({ timeout: 45000 });

    // 4. 驗證失敗狀態的 UI
    // 由於轉錄會立即失敗，狀態可能非常短暫，我們直接檢查最終的失敗狀態
    await expect(failedTaskLocator.locator('.task-status')).toContainText('失敗');

    // 清理臨時檔案
    fs.unlinkSync(fakeFileName);
  });
});
