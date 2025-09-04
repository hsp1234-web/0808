// @ts-check
import { test, expect } from '@playwright/test';

// 測試套件的描述
test.describe('完整端對端驗證', () => {
  const YOUTUBE_URL = 'https://www.youtube.com/watch?v=YE7VzlLtp-4'; // Big Buck Bunny

  // 測試案例：驗證媒體下載與預覽功能
  test('應能成功下載影片並顯示預覽', async ({ page }) => {
    // 增加測試的總體超時時間，因為下載可能需要一些時間
    test.setTimeout(120000); // 120 秒

    // 1. 導覽至應用程式頁面
    await page.goto('/'); // Use the baseURL from the config

    // 2. 切換到「媒體下載器」分頁
    await page.getByRole('link', { name: '📥 媒體下載器' }).click();

    // 驗證下載器分頁是否可見
    await expect(page.locator('#downloader-tab')).toBeVisible();

    // 3. 輸入 YouTube 影片的 URL
    // 選擇影片下載類型
    await page.locator('input[name="download-type"][value="video"]').check();
    await page.locator('#downloader-urls-input').fill(YOUTUBE_URL);

    // 4. 點擊「開始下載」按鈕
    await page.locator('#start-download-btn').click();

    // 5. 等待下載完成
    // 我們將等待包含影片標題的任務項目出現，並顯示「預覽」按鈕
    // 這表示任務已成功完成
    const completedTaskLocator = page.locator('#downloader-tasks .task-item', {
      has: page.locator('.task-filename:text-is("Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film")'),
      hasNot: page.locator('.task-status:text-is("下載中...")')
    });

    // 等待元素出現，設置較長的超時時間
    await completedTaskLocator.waitFor({ state: 'visible', timeout: 90000 }); // 90 秒

    // 6. 點擊該項目的「預覽」按鈕
    await completedTaskLocator.locator('a.btn-preview').click();

    // 7. 驗證預覽彈出視窗（modal）
    const modal = page.locator('#preview-modal');
    await expect(modal).toBeVisible();

    // 驗證 modal 中是否包含一個 video 元素
    const videoElement = modal.locator('video');
    await expect(videoElement).toBeVisible();
    await expect(videoElement).toHaveAttribute('src', /^\/media\/uploads\/Big Buck Bunny/);

    // 8. 擷取螢幕截圖
    await page.screenshot({ path: 'verification_screenshot.jpg', fullPage: true });

    // 增加一個日誌點，確認測試已達此處
    console.log('測試完成，已成功擷取螢幕截圖。');
  });
});
