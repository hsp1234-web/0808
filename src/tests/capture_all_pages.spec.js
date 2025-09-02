// @ts-check
import { test, expect } from '@playwright/test';

const pages = [
  { name: 'index', path: '/static/index.html' },
  { name: 'transcribe', path: '/static/transcribe.html' },
  { name: 'downloader', path: '/static/downloader.html' },
  { name: 'youtube_report', path: '/static/youtube_report.html' },
  { name: 'prompts', path: '/static/prompts.html' },
];

const viewports = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'mobile', width: 393, height: 851 }, // iPhone 14 Pro viewport
];

// 為測試準備的模擬任務資料
const mockTasks = [
    { task_id: 'task-1', type: 'transcribe', status: 'processing', message: '轉錄中... 50%', payload: { original_filename: '一個很長的音檔名稱用來測試排版.mp3' }, startTime: Date.now() - 30000 },
    { task_id: 'task-2', type: 'download', status: 'generating', message: '下載中...', payload: { original_filename: '教學影片.mp4' }, startTime: Date.now() - 120000 },
    { task_id: 'task-3', type: 'transcribe', status: 'completed', result: { transcript_path: 'path/to/transcript.txt', output_path: '/api/download/task-3?type=media' }, payload: { original_filename: '會議紀錄.wav' } },
    {
        task_id: 'task-4',
        type: 'gemini_process',
        status: 'completed',
        result: {
            video_title: 'AI 趨勢分析報告',
            output_path: '/api/download/task-4?type=artifact', // Path to the HTML report
            processing_duration_seconds: 123.45,
            total_tokens_used: 5678
        }
    },
    { task_id: 'task-5', type: 'transcribe', status: 'failed', error: '音訊格式無法辨識', payload: { original_filename: '損毀的檔案.aac' } },
];


test.describe('全頁面視覺驗證 (桌面與手機，含模擬資料)', () => {
  for (const pageInfo of pages) {
    for (const viewport of viewports) {
      test(`擷取 ${pageInfo.name} 頁面的 ${viewport.name} 視圖 (含資料)`, async ({ page }) => {
        // 設定視窗大小
        await page.setViewportSize({ width: viewport.width, height: viewport.height });

        // 前往頁面
        await page.goto(`http://127.0.0.1:42649${pageInfo.path}`, { waitUntil: 'networkidle' });

        // 等待WebSocket連線成功
        await expect(page.locator('#status-light')).toHaveClass(/status-green/, { timeout: 15000 });

        // 注入模擬任務資料
        await page.evaluate((tasks) => {
            window.__updateTestState({ tasks });
        }, mockTasks);

        // 給予一小段額外時間讓UI渲染完成
        await page.waitForTimeout(500);

        // 擷取螢幕截圖
        await page.screenshot({
          path: `${pageInfo.name}-page-${viewport.name}-populated.jpg`,
          fullPage: true,
          quality: 90,
          type: 'jpeg'
        });
      });
    }
  }
});
