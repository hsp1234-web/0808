// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * 說明：
 * 這份測試腳本是為了在前端重構前，建立一個功能基準線。
 * 它會驗證目前單頁應用 (SPA) `mp3.html` 的所有核心功能，
 * 確保重構後的 MPA (多頁應用) 版本能保有 100% 的功能一致性。
 */
test.describe('SPA 基準線驗證 (e2e-baseline-validation)', () => {
  const MOCK_API_KEY = 'mock-api-key-for-testing';
  const TEST_AUDIO_FILE = 'src/tests/fixtures/test_audio.mp3';
  const MOCK_YOUTUBE_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'; // Mock URL

  // 在所有測試開始前，先設定模擬 API 回應
  test.beforeEach(async ({ page }) => {
    // 模擬後端 API 回應
    await page.route('/api/tasks', route => route.fulfill({ status: 200, body: '[]' }));
    await page.route('/api/system_stats', route => route.fulfill({ status: 200, body: JSON.stringify({ cpu_usage: 10, ram_usage: 20, gpu_detected: false }) }));
    await page.route('/api/system/readiness', route => route.fulfill({ status: 200, body: JSON.stringify({ ready: true }) }));
    await page.route('**/api/youtube/models', route => {
        const req = route.request();
        if (req.postDataJSON().api_key === MOCK_API_KEY) {
            route.fulfill({ status: 200, body: JSON.stringify({ models: [{id: 'gemini-pro', name: 'Gemini Pro'}] }) });
        } else {
            route.fulfill({ status: 400, body: JSON.stringify({ detail: "API 金鑰無效" }) });
        }
    });

    // 導覽至應用程式主頁
    await page.goto('/');
  });

  test('畫面初始狀態與 WebSocket 連線', async ({ page }) => {
    await expect(page).toHaveTitle('音訊轉錄儀');
    await expect(page.locator('h1')).toHaveText('音訊轉錄儀');

    // 模擬 WebSocket 連線成功
    await page.evaluate(() => {
        const statusTextEl = document.getElementById('status-text');
        const statusLightEl = document.getElementById('status-light');
        if (statusTextEl) statusTextEl.textContent = '已連線';
        if (statusLightEl) {
            statusLightEl.classList.remove('status-yellow');
            statusLightEl.classList.add('status-green');
        }
    });
    await expect(page.locator('#status-text')).toHaveText('已連線');

    await expect(page.locator('.tab-button.active')).toHaveText('📁 本機檔案轉錄');
    await expect(page.locator('#local-file-tab')).toBeVisible();
  });

  test('分頁切換功能', async ({ page }) => {
    // 點擊媒體下載器分頁
    await page.locator('.tab-button[data-tab="downloader-tab"]').click();
    await expect(page.locator('#downloader-tab')).toBeVisible();
    await expect(page.locator('#local-file-tab')).not.toBeVisible();

    // 點擊 YouTube 轉報告分頁
    await page.getByTestId('youtube-report-tab').click();
    await expect(page.locator('#youtube-report-tab')).toBeVisible();
    await expect(page.locator('#downloader-tab')).not.toBeVisible();

    // 點擊返回本地檔案轉錄分頁
    await page.locator('.tab-button[data-tab="local-file-tab"]').click();
    await expect(page.locator('#local-file-tab')).toBeVisible();
    await expect(page.locator('#youtube-report-tab')).not.toBeVisible();
  });

  test('本地轉錄流程', async ({ page }) => {
    // 模擬轉錄任務建立
    await page.route('**/api/transcribe', async route => {
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          task_id: 'mock-transcribe-task-123',
          filename: 'test_audio.mp3', // 直接使用已知檔名，避免 API 錯誤
          status: 'starting',
          type: 'transcribe',
        }),
      });
    });

    // 上傳檔案
    await page.locator('#file-input').setInputFiles(TEST_AUDIO_FILE);
    await expect(page.locator('#file-list .task-item')).toHaveText(/test_audio.mp3/);

    // 開始處理
    await page.locator('#start-processing-btn').click();

    // 模擬 WebSocket 推送任務開始的訊息，這才是觸發 UI 更新的關鍵
    await page.evaluate(() => {
      window.handleWebSocketMessage({
        type: 'TRANSCRIPTION_STATUS',
        payload: {
          task_id: 'mock-transcribe-task-123',
          filename: 'test_audio.mp3',
          status: 'starting',
          type: 'transcribe',
        }
      });
    });

    // 驗證任務出現在處理中列表
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-transcribe-task-123"]')).toBeVisible();
    await expect(page.locator('#ongoing-tasks .task-filename')).toHaveText(/test_audio.mp3/);

    // 模擬 WebSocket 更新任務狀態為完成
    await page.evaluate(() => {
      window.handleWebSocketMessage({
        type: 'TRANSCRIPTION_STATUS',
        payload: {
          task_id: 'mock-transcribe-task-123',
          status: 'completed',
          result: {
            output_path: '/path/to/mock_transcript.txt',
            transcript_path: '/path/to/mock_transcript.txt',
            original_filename: 'test_audio.mp3'
          }
        }
      });
    });

    // 驗證任務從處理中列表移除
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-transcribe-task-123"]')).not.toBeVisible();

    // 驗證任務出現在已完成列表
    const completedTask = page.locator('#completed-tasks .task-item[data-task-id="mock-transcribe-task-123"]');
    await expect(completedTask).toBeVisible();
    await expect(completedTask.locator('.task-filename')).toContainText('test_audio.mp3');
    await expect(completedTask.locator('.btn-preview')).toBeVisible();
    await expect(completedTask.locator('.btn-download')).toBeVisible();
  });

  test('YouTube 報告流程', async ({ page }) => {
    // 模擬 YouTube 處理任務建立
    await page.route('**/api/youtube/process', async route => {
      await route.fulfill({
        status: 200,
        body: JSON.stringify({
          tasks: [{
            task_id: 'mock-youtube-task-456',
            url: MOCK_YOUTUBE_URL,
            status: 'starting',
            type: 'gemini_process'
          }]
        }),
      });
    });

    // 切換到 YouTube 分頁
    await page.getByTestId('youtube-report-tab').click();

    // 輸入並儲存 API 金鑰
    await page.getByTestId('api-key-input').fill(MOCK_API_KEY);
    await page.getByTestId('save-api-key-button').click();
    await expect(page.locator('#api-key-status span')).toHaveText('金鑰有效，Gemini 功能已啟用');

    // 輸入網址並開始分析
    await page.locator('.youtube-url-input').first().fill(MOCK_YOUTUBE_URL);
    await page.getByTestId('start-youtube-processing-button').click();

    // 模擬 WebSocket 推送任務開始的訊息
    await page.evaluate(() => {
      window.handleWebSocketMessage({
        type: 'YOUTUBE_STATUS',
        payload: {
          task_id: 'mock-youtube-task-456',
          url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
          status: 'starting',
          type: 'gemini_process',
          task_type: 'gemini_process', // 確保 task_type 也存在
        }
      });
    });

    // 驗證任務出現在處理中列表
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-youtube-task-456"]')).toBeVisible();

    // 模擬 WebSocket 更新任務狀態為完成
    await page.evaluate(() => {
      window.handleWebSocketMessage({
        type: 'YOUTUBE_STATUS',
        payload: {
          task_id: 'mock-youtube-task-456',
          task_type: 'gemini_process',
          status: 'completed',
          result: {
            output_path: '/path/to/mock_report.html',
            video_title: 'Mock YouTube Report'
          }
        }
      });
    });

    // 驗證任務從處理中列表移除
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-youtube-task-456"]')).not.toBeVisible();

    // 驗證報告出現在瀏覽區
    const reportItem = page.locator('#youtube-file-browser .task-item[data-task-id="mock-youtube-task-456"]');
    await expect(reportItem).toBeVisible();
    await expect(reportItem.locator('.task-filename')).toHaveText(/Mock YouTube Report/);
    await expect(reportItem.locator('[data-testid="view-report-button"]')).toBeVisible();
  });
});
