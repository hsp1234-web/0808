const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');

// 使用者指定的 API 金鑰用於本次特別測試
const GOOGLE_API_KEY = "AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU";
const YOUTUBE_URL = "https://youtube.com/shorts/mG5z-pfhIiA?si=rIHZPsD_VpbgGeFt";
const BILIBILI_URL = "https://b23.tv/xALqLQM";
// 使用者指定的模型名稱，測試腳本會嘗試尋找包含此字串的選項
const TARGET_MODEL_NAME_PARTIAL = "Flash-Lite Preview";

if (!GOOGLE_API_KEY) {
  throw new Error("測試執行失敗：API 金鑰未設定。");
}

test.describe('使用者指定的手動測試案例', () => {
  let serverProcess;
  let serverReady = false;
  let serverUrl;

  test.beforeAll(async () => {
    const pythonPath = process.env.PYENV_ROOT ? `${process.env.PYENV_ROOT}/shims/python` : 'python3';
    // 啟動後端伺服器，並傳入 API 金鑰
    // 修正：執行正確的伺服器啟動腳本，與 playwright.config.js 保持一致
    // 終極手段：使用 detached: true 模式，讓伺服器在獨立的進程組中運行，避免被不明信號干擾
    serverProcess = spawn(pythonPath, ['-u', 'scripts/run_server_for_playwright.py'], {
      detached: true,
      env: { ...process.env, GOOGLE_API_KEY: GOOGLE_API_KEY },
    });

    // 監聽後端日誌以獲取代理 URL
    serverProcess.stdout.on('data', (data) => {
      process.stdout.write(`[Orchestrator STDOUT]: ${data}`);
      // 修正：使用正規表示式來更穩健地解析 URL，避免換行符等不可見字元問題
      const urlMatch = data.toString().match(/PROXY_URL:\s*(http:\/\/\S+)/);
      if (urlMatch && urlMatch[1]) {
        serverUrl = urlMatch[1];
        console.log(`[Test] 偵測到伺服器 URL: ${serverUrl}`);
        serverReady = true;
      }
    });

    serverProcess.stderr.on('data', (data) => {
      process.stderr.write(`[Orchestrator STDERR]: ${data}`);
    });

    // 等待伺服器就緒，並加入健康檢查
    const startTime = Date.now();
    while (Date.now() - startTime < 60000) { // 總共等待 60 秒
      if (serverUrl) {
        try {
          // 使用 fetch 進行健康檢查
          const response = await fetch(`${serverUrl}/api/health`);
          if (response.status === 200) {
            console.log('[Test] ✅ 健康檢查成功，伺服器已就緒。');
            serverReady = true;
            break;
          }
        } catch (e) {
          // 忽略連線被拒絕等錯誤，繼續重試
        }
      }
      await new Promise(resolve => setTimeout(resolve, 1000)); // 每秒檢查一次
    }

    if (!serverReady) {
      throw new Error('伺服器在 60 秒內未能啟動或通過健康檢查。');
    }
  });

  test.afterAll(() => {
    if (serverProcess) {
      console.log('正在終止伺服器進程...');
      serverProcess.kill('SIGINT');
    }
  });

  test('應能成功處理 Bilibili 影片並驗證預覽與資訊功能', async ({ page }) => {
    await page.goto(serverUrl);
    await page.getByTestId('youtube-report-tab').click();

    // 設定 API 金鑰並載入模型
    await page.getByTestId('api-key-input').fill(GOOGLE_API_KEY);
    await page.getByTestId('save-api-key-button').click();
    await expect(page.getByText('模型載入成功')).toBeVisible({ timeout: 20000 });

    // 選擇指定的模型
    await page.getByTestId('gemini-model-select').selectOption({ label: new RegExp(TARGET_MODEL_NAME_PARTIAL) });
    const selectedModel = await page.getByTestId('gemini-model-select').inputValue();
    console.log(`[Test] 已選擇模型: ${selectedModel}`);


    // 新增 Bilibili 任務
    await page.getByTestId('add-youtube-row-button').click();
    await page.locator('.url-input-group input').nth(0).fill(BILIBILI_URL);

    await page.getByTestId('start-youtube-processing-button').click();

    // 等待 Bilibili 任務成功
    const bilibiliTaskRow = page.locator('.task-row').filter({ hasText: 'b23.tv' });
    await expect(bilibiliTaskRow.getByTestId('task-status-badge-completed')).toBeVisible({ timeout: 240000 });

    // 驗證「詳細資訊」功能 (點擊任務本身)
    await bilibiliTaskRow.click();
    await expect(page.getByTestId('task-detail-modal')).toBeVisible();
    await expect(page.getByTestId('task-detail-content')).toContainText('audio');
    await expect(page.getByTestId('task-detail-content')).toContainText('b23.tv');
    await page.getByTestId('task-detail-close-button').click();
    await expect(page.getByTestId('task-detail-modal')).not.toBeVisible();
    console.log('[Test] ✅ 詳細資訊功能驗證成功。');


    // 驗證「預覽報告」功能
    await bilibiliTaskRow.getByTestId('view-report-button').click();
    await expect(page.getByTestId('report-modal')).toBeVisible();
    await expect(page.getByTestId('report-content-html')).toContainText(/AI 學習總結報告/);
    await expect(page.getByTestId('report-token-usage')).toContainText(/總 Token 數/);
    await expect(page.getByTestId('report-download-button')).toBeVisible();
    await expect(page.getByTestId('report-preview-button')).toBeVisible();
    console.log('[Test] ✅ 預覽報告功能驗證成功。');

    // 截圖驗證
    await page.screenshot({ path: 'user-request-test-final-state.jpg', fullPage: true });
  });
});
