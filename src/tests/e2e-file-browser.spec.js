import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

// --- JULES: ESM-compatible way to get __dirname ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 定義測試檔案的路徑和內容
const UPLOADS_DIR = path.join(__dirname, '..', '..', 'uploads');
const TEST_FILENAME = `test-file-for-browser-${Date.now()}.txt`;
const TEST_FILE_PATH = path.join(UPLOADS_DIR, TEST_FILENAME);
const TEST_FILE_CONTENT = 'This is a test file for the file browser feature.';

test.describe('File Browser Feature', () => {

  test('should create a file, list it, allow deletion, and update the UI', async ({ page }) => {
    // 將檔案建立和刪除移至測試案例內部，以避免生命週期鉤子和伺服器清理流程的衝突

    // 1. 建立測試檔案
    if (!fs.existsSync(UPLOADS_DIR)){
        fs.mkdirSync(UPLOADS_DIR, { recursive: true });
    }
    fs.writeFileSync(TEST_FILE_PATH, TEST_FILE_CONTENT);

    try {
      // 2. 導航到主頁並強制重新整理以確保檔案系統同步
      await page.goto('/');
      // 等待一個已知元素出現，表示頁面已基本載入
      await expect(page.locator('h1')).toContainText('音訊轉錄儀', { timeout: 10000 });
      // 執行重新整理
      await page.reload({ waitUntil: 'networkidle' });

      // 3. 找到檔案總管區塊，並等待我們的測試檔案出現
      const fileBrowserList = page.locator('#file-browser-list');
      const fileItem = fileBrowserList.locator('.task-item', { hasText: TEST_FILENAME });

      // 斷言：確認檔案項目在頁面上可見
      await expect(fileItem).toBeVisible({ timeout: 10000 });

      // 斷言：確認檔案名稱和大小資訊是正確的
      await expect(fileItem.getByText(TEST_FILENAME)).toBeVisible();
      await expect(fileItem.locator('small')).toContainText('B');

      // 4. 處理刪除操作
      page.on('dialog', dialog => {
        expect(dialog.message()).toContain(`您確定要永久刪除檔案 "${TEST_FILENAME}" 嗎？`);
        dialog.accept();
      });

      // 找到並點擊刪除按鈕
      const deleteButton = fileItem.locator('a:has-text("刪除")');
      await deleteButton.click();

      // 5. 驗證 UI 更新
      await expect(fileItem).not.toBeVisible({ timeout: 5000 });

      // 6. 驗證後端狀態
      await page.reload({ waitUntil: 'networkidle' });

      const reloadedFileItem = page.locator('#file-browser-list .task-item', { hasText: TEST_FILENAME });
      await expect(reloadedFileItem).not.toBeVisible();

    } finally {
      // 7. 清理測試檔案，確保無論測試成功或失敗都會執行
      if (fs.existsSync(TEST_FILE_PATH)) {
        fs.unlinkSync(TEST_FILE_PATH);
      }
    }
  });
});
