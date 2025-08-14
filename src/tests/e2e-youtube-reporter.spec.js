// src/tests/e2e-youtube-reporter.spec.js

import { test, expect } from '@playwright/test';

test.describe('YouTube Reporter Component E2E Test', () => {

  // 在每個測試前，都先導航到主頁
  test.beforeEach(async ({ page }) => {
    // 監聽並模擬後端 API
    await page.route('/api/youtube/validate_api_key', async route => {
      const requestBody = route.request().postDataJSON();
      if (requestBody.api_key === 'valid-key') {
        await route.fulfill({ json: { valid: true } });
      } else {
        await route.fulfill({ status: 400, json: { valid: false, detail: 'API 金鑰無效。' } });
      }
    });

    await page.route('/api/youtube/models', async route => {
      await route.fulfill({ json: { models: [{ id: 'gemini-1.5-flash-mock', name: 'Gemini 1.5 Flash (模擬)' }] } });
    });

    await page.route('/api/youtube/process', async route => {
      await route.fulfill({ json: { message: '已成功建立任務。', tasks: [] } });
    });

    await page.route('/api/log/action', async route => {
        await route.fulfill({ status: 200, json: { status: 'logged' } });
    });

    await page.goto('/');
    // 點擊 "YouTube 轉報告" 頁籤，以確保該元件可見
    await page.locator('button[data-tab="youtube-report-tab"]').click();
  });

  test('應能正確渲染 YouTube Reporter 的 UI 元素', async ({ page }) => {
    // 檢查標題是否存在
    await expect(page.locator('h2:has-text("Google API 金鑰管理")')).toBeVisible();

    // 檢查 API Key 輸入框和按鈕
    await expect(page.locator('#api-key-input')).toBeVisible();
    await expect(page.locator('button:has-text("儲存金鑰")')).toBeVisible();
    await expect(page.locator('button:has-text("清除金鑰")')).toBeVisible();

    // 檢查 YouTube URL 輸入區域
    await expect(page.locator('h2:has-text("輸入 YouTube 影片")')).toBeVisible();
    await expect(page.locator('.youtube-url-input')).toHaveCount(1);
    await expect(page.locator('button:has-text("+ 新增一列")')).toBeVisible();

    // 檢查參數和操作按鈕
    await expect(page.locator('h2:has-text("參數控制區")')).toBeVisible();
    await expect(page.locator('button:has-text("僅下載音訊")')).toBeVisible();
    await expect(page.locator('button:has-text("分析影片 (Gemini)")')).toBeDisabled();
  });

  test('API 金鑰驗證流程應能正常運作', async ({ page }) => {
    const apiKeyInput = page.locator('#api-key-input');
    const saveBtn = page.locator('button:has-text("儲存金鑰")');
    const clearBtn = page.locator('button:has-text("清除金鑰")');
    const statusText = page.locator('#api-key-status span');
    const processBtn = page.locator('button:has-text("分析影片 (Gemini)")');
    const paramsFieldset = page.locator('#youtube-params-fieldset');

    // 1. 測試無效金鑰
    await apiKeyInput.fill('invalid-key');
    await saveBtn.click();
    // JULES'S FIX: 更新斷言以匹配 UI 實際顯示的更詳細的錯誤訊息
    await expect(statusText).toHaveText('金鑰無效或發生未知錯誤');
    await expect(processBtn).toBeDisabled();
    // 使用 toHaveAttribute 進行更穩健的檢查
    await expect(paramsFieldset).toHaveAttribute('disabled', '');

    // 2. 測試有效金鑰
    await apiKeyInput.fill('valid-key');
    await saveBtn.click();
    await expect(statusText).toHaveText('金鑰有效，Gemini 功能已啟用');
    await expect(processBtn).toBeEnabled();
    await expect(paramsFieldset).toBeEnabled();

    // 3. 測試清除金鑰
    await clearBtn.click();
    await expect(statusText).toHaveText('尚未提供金鑰');
    await expect(processBtn).toBeDisabled();
    await expect(paramsFieldset).toBeDisabled();
    await expect(apiKeyInput).toBeEmpty();
  });

  test('應能新增和移除 YouTube URL 輸入列', async ({ page }) => {
    const addBtn = page.locator('button:has-text("+ 新增一列")');

    await expect(page.locator('.youtube-link-row')).toHaveCount(1);

    await addBtn.click();
    await expect(page.locator('.youtube-link-row')).toHaveCount(2);

    await addBtn.click();
    await expect(page.locator('.youtube-link-row')).toHaveCount(3);

    // 移除第二列
    await page.locator('.youtube-link-row').nth(1).locator('.remove-youtube-row-btn').click();
    await expect(page.locator('.youtube-link-row')).toHaveCount(2);

    // 移除剩下的兩列
    await page.locator('.youtube-link-row').nth(0).locator('.remove-youtube-row-btn').click();
    await page.locator('.youtube-link-row').nth(0).locator('.remove-youtube-row-btn').click();

    // 應當還剩下一列
    await expect(page.locator('.youtube-link-row')).toHaveCount(1);
  });

  test('點擊分析按鈕時應發送正確的 API 請求', async ({ page }) => {
    // 先設定有效的 API Key
    await page.locator('#api-key-input').fill('valid-key');
    await page.locator('button:has-text("儲存金鑰")').click();

    // 填寫 URL 和檔名
    await page.locator('.youtube-url-input').first().fill('https://www.youtube.com/watch?v=test1');
    await page.locator('.youtube-filename-input').first().fill('測試影片一');

    await page.locator('button:has-text("+ 新增一列")').click();
    await page.locator('.youtube-url-input').nth(1).fill('https://www.youtube.com/watch?v=test2');

    // 攔截 /api/youtube/process 請求
    const apiRequestPromise = page.waitForRequest('/api/youtube/process');

    // 點擊分析按鈕
    await page.locator('button:has-text("分析影片 (Gemini)")').click();

    const request = await apiRequestPromise;
    const requestBody = request.postDataJSON();

    // 驗證請求內容
    expect(requestBody.download_only).toBe(false);
    expect(requestBody.model).toBe('gemini-1.5-flash-mock');
    expect(requestBody.requests).toEqual([
      { url: 'https://www.youtube.com/watch?v=test1', filename: '測試影片一' },
      { url: 'https://www.youtube.com/watch?v=test2', filename: '' },
    ]);
  });
});
