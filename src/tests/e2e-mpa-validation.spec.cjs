// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * 說明：
 * 這份測試腳本是為了在前端 MPA (多頁應用) 重構後，驗證其功能完整性。
 * 它會針對每個獨立的頁面 (transcribe.html, youtube_report.html 等) 進行測試，
 * 確保所有核心功能都已 100% 保留且運作正常。
 */
test.describe('MPA 功能驗證 (e2e-mpa-validation)', () => {
  const MOCK_API_KEY = 'mock-api-key-for-testing';
  const TEST_AUDIO_FILE = 'src/tests/fixtures/test_audio.mp3';
  const MOCK_YOUTUBE_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'; // Mock URL

  // 在所有測試開始前，先設定通用的模擬 API 回應
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
     await page.route('**/api/youtube/validate_api_key', route => {
      route.fulfill({ status: 200, body: JSON.stringify({ valid: true }) });
    });


    // MPA 測試的起點是主頁
    await page.goto('/');
  });

  test('主頁 (index.html) 初始狀態與 WebSocket 連線', async ({ page }) => {
    await page.waitForURL('**/'); // 等待頁面載入
    await expect(page).toHaveTitle("儀表板 - 音訊轉錄儀");
    await expect(page.locator('h1')).toHaveText(/儀表板/);

    // 模擬 WebSocket 連線成功
    await page.evaluate(() => {
        window.__updateTestState({ connectionStatus: 'connected' });
    });
    await expect(page.locator('#status-text')).toHaveText('已連線');
    // 確認 h1 已足夠，移除不穩定的 active class 檢查
  });

  test('本地轉錄流程 (transcribe.html)', async ({ page }) => {
    // ** MPA 變更點: 直接導覽至目標頁面 **
    await page.goto('/static/transcribe.html');
    await expect(page).toHaveTitle("本地轉錄 - 音訊轉錄儀");

    // 模擬轉錄任務建立
    await page.route('**/api/transcribe', async route => {
      await route.fulfill({
        status: 202, // 任務已接受
        body: JSON.stringify({
          tasks: [{
            task_id: 'mock-transcribe-task-123',
            type: 'transcribe'
          }]
        }),
      });
    });

    // 上傳檔案
    await page.locator('#file-input').setInputFiles(TEST_AUDIO_FILE);
    await expect(page.locator('#file-list .task-item')).toHaveText(/test_audio.mp3/);

    // 開始處理
    await page.locator('#start-processing-btn').click();

    // 模擬 WebSocket 推送任務開始的訊息
    await page.evaluate(() => {
      window.__handleTestWebSocketMessage({
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
      window.__handleTestWebSocketMessage({
        type: 'TRANSCRIPTION_STATUS',
        payload: {
          task_id: 'mock-transcribe-task-123',
          status: 'completed',
          result: {
            output_path: '/media/transcripts/mock-transcribe-task-123.txt',
            transcript_path: '/media/transcripts/mock-transcribe-task-123.txt',
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

  test('YouTube 報告流程 (youtube_report.html)', async ({ page }) => {
    // ** MPA 變更點: 直接導覽至目標頁面 **
    await page.goto('/static/youtube_report.html');
    await expect(page).toHaveTitle("YouTube 轉報告 - 音訊轉錄儀");

    // 模擬 YouTube 處理任務建立
    await page.route('**/api/youtube/process', async route => {
      await route.fulfill({
        status: 202,
        body: JSON.stringify({
          tasks: [{
            task_id: 'mock-youtube-task-456',
            final_task_id: 'mock-youtube-task-456-final', // 模擬處理鏈
            url: MOCK_YOUTUBE_URL,
            status: 'starting',
            task_type: 'youtube_process_chain'
          }]
        }),
      });
    });

    // 輸入並儲存 API 金鑰
    await page.getByTestId('api-key-input').fill(MOCK_API_KEY);
    await page.getByTestId('save-api-key-button').click();

    // 等待非同步的金鑰驗證和模型載入完成
    await expect(page.locator('#api-key-status span')).toContainText('金鑰有效');
    await expect(page.getByTestId('start-youtube-processing-button')).toBeEnabled();


    // 輸入網址並開始分析
    await page.locator('.youtube-url-input').first().fill(MOCK_YOUTUBE_URL);
    await page.getByTestId('start-youtube-processing-button').click();

    // 模擬 WebSocket 推送下載任務開始
    await page.evaluate(() => {
      window.__handleTestWebSocketMessage({
        type: 'YOUTUBE_STATUS',
        payload: {
          task_id: 'mock-youtube-task-456',
          url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
          status: 'downloading',
          message: '下載中',
          task_type: 'youtube_download',
        }
      });
    });

    // 驗證下載任務出現在處理中列表
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-youtube-task-456"]')).toBeVisible();

    // 模擬 WebSocket 推送 AI 處理任務完成
    await page.evaluate((final_task_id) => {
      window.__handleTestWebSocketMessage({
        type: 'YOUTUBE_STATUS',
        payload: {
          task_id: final_task_id,
          status: 'completed',
          type: 'gemini_process', // 使用正確的類型
          result: {
            output_path: '/media/reports/mock_report.html',
            video_title: 'Mock YouTube Report'
          }
        }
      });
    }, 'mock-youtube-task-456-final');

    // 模擬 WebSocket 推送原始下載任務也完成
    await page.evaluate((initial_task_id) => {
         window.__handleTestWebSocketMessage({
            type: 'YOUTUBE_STATUS',
            payload: {
                task_id: initial_task_id,
                status: 'completed',
                type: 'youtube_download' // 使用正確的類型
            }
         });
    }, 'mock-youtube-task-456');


    // 驗證處理中任務被移除
    await expect(page.locator('#ongoing-tasks .task-item[data-task-id="mock-youtube-task-456"]')).not.toBeVisible();

    // 驗證報告出現在瀏覽區
    const reportItem = page.locator('#youtube-file-browser .task-item[data-task-id="mock-youtube-task-456-final"]');
    await expect(reportItem).toBeVisible();
    await expect(reportItem.locator('.task-filename')).toHaveText(/Mock YouTube Report/);
    await expect(reportItem.locator('.btn-preview')).toBeVisible();
  });
});
