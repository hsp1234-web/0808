const { test, expect } = require('@playwright/test');
const { spawn } = require('child_process');
const path = require('path');

// TEMPORARY: Hardcoding the key to get around environment variable issues.
// This will be reverted immediately after the test run.
const GOOGLE_API_KEY = "AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU";

if (!GOOGLE_API_KEY) {
  throw new Error("測試執行失敗：API 金鑰未設定。");
}

const YOUTUBE_URL = "https://youtube.com/shorts/mG5z-pfhIiA?si=rIHZPsD_VpbgGeFt";
const BILIBILI_URL = "https://b23.tv/xALqLQM";
const ALL_REPORT_OPTIONS = ["summary", "transcript", "translate", "translate_zh"];

test.describe('真實 YouTube/Bilibili 處理流程端對端測試', () => {
  let serverProcess;
  let serverReady = false;
  let serverUrl;

  test.beforeAll(async () => {
    const pythonPath = process.env.PYENV_ROOT ? `${process.env.PYENV_ROOT}/shims/python` : 'python3';
    serverProcess = spawn(pythonPath, ['-u', 'src/main.py', '--mode=real'], {
      env: { ...process.env, GOOGLE_API_KEY: GOOGLE_API_KEY },
    });

    serverProcess.stdout.on('data', (data) => {
      process.stdout.write(`[Orchestrator STDOUT]: ${data}`);
      if (data.toString().includes('PROXY_URL:')) {
        serverUrl = data.toString().split('PROXY_URL:')[1].trim();
        console.log(`[Test] 偵測到伺服器 URL: ${serverUrl}`);
        serverReady = true;
      }
    });

    serverProcess.stderr.on('data', (data) => {
      process.stderr.write(`[Orchestrator STDERR]: ${data}`);
    });

    for (let i = 0; i < 60; i++) {
      if (serverReady) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    if (!serverReady) {
      throw new Error('伺服器在 60 秒內未能啟動。');
    }
  });

  test.afterAll(() => {
    if (serverProcess) {
      console.log('正在終止伺服器進程...');
      serverProcess.kill('SIGINT');
    }
  });

  test('應能處理 Bilibili 影片並正確顯示 YouTube 錯誤', async ({ page }) => {
    await page.goto(serverUrl);
    await page.getByTestId('youtube-report-tab').click();

    // 清空任務並設定 API 金鑰
    await page.getByTestId('debug-clear-tasks-button').click();
    await expect(page.locator('.task-row')).toHaveCount(0);
    await page.getByTestId('api-key-input').fill(GOOGLE_API_KEY);
    await page.getByTestId('save-api-key-button').click();
    await expect(page.getByText('模型載入成功')).toBeVisible({ timeout: 20000 });

    // 新增兩個 URL 輸入框
    await page.getByTestId('add-youtube-row-button').click();
    await page.getByTestId('add-youtube-row-button').click();

    // 填入 URL
    await page.locator('.url-input-group input').nth(0).fill(YOUTUBE_URL);
    await page.locator('.url-input-group input').nth(1).fill(BILIBILI_URL);

    // 選擇所有報告選項
    for (const option of ALL_REPORT_OPTIONS) {
      await page.locator(`.report-options-group input[value="${option}"]`).nth(0).check();
      await page.locator(`.report-options-group input[value="${option}"]`).nth(1).check();
    }

    await page.getByTestId('start-youtube-processing-button').click();

    // 等待並驗證 YouTube 任務失敗
    const youtubeTaskRow = page.locator('.task-row').filter({ hasText: 'youtube.com' });
    await expect(youtubeTaskRow.getByTestId('task-status-badge-failed')).toBeVisible({ timeout: 90000 });
    await expect(youtubeTaskRow).toContainText(/403|Forbidden|下載被拒/i);

    // 等待並驗證 Bilibili 任務成功
    const bilibiliTaskRow = page.locator('.task-row').filter({ hasText: 'b23.tv' });
    await expect(bilibiliTaskRow.getByTestId('task-status-badge-completed')).toBeVisible({ timeout: 240000 });

    // 驗證 Bilibili 報告細節
    await bilibiliTaskRow.getByTestId('view-report-button').click();
    await expect(page.getByTestId('report-modal')).toBeVisible();
    await expect(page.getByTestId('report-content-html')).toContainText(/AI 學習總結報告/);
    await expect(page.getByTestId('report-token-usage')).toContainText(/總 Token 數/);
    await expect(page.getByTestId('report-download-button')).toBeVisible();
    await expect(page.getByTestId('report-preview-button')).toBeVisible();

    // 截圖驗證
    await page.screenshot({ path: 'e2e-real-youtube-test-final-state.png', fullPage: true });
  });
});
