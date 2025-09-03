import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Main Validation Suite', () => {
  test('should successfully process a local audio file after fixing dependencies', async ({ page }) => {
    // 1. Navigate to the application
    await page.goto('/');
    // Corrected title assertion
    await expect(page).toHaveTitle(/音訊轉錄儀/);

    // 2. Switch to the Local File Transcription tab
    await page.getByRole('tab', { name: '本機檔案轉錄' }).click();

    // 3. Upload the mock audio file
    const audioFilePath = path.join(__dirname, 'fixtures', 'test_audio.mp3');
    await page.locator('input[type="file"]').setInputFiles(audioFilePath);

    // Wait for the file to be recognized by the UI
    await expect(page.locator('.file-info-name')).toContainText('test_audio.mp3');

    // 4. Select the model
    // Assuming a data-testid is available for the model selector
    await page.locator('[data-testid="model-select"]').selectOption('tiny');

    // 5. Start the process
    await page.getByRole('button', { name: '開始處理' }).click();

    // 6. Assertion: Wait for the task to complete
    const taskRow = page.locator('[data-testid^="task-row-"]').first();
    await expect(taskRow).toBeVisible({ timeout: 10000 });
    const statusLocator = taskRow.locator('[data-testid^="task-status-"]');
    await expect(statusLocator).toContainText('已完成', { timeout: 60000 });

    // 7. Final Verification Screenshot
    await page.screenshot({ path: 'test-results/e2e_main_validation_success.jpg', fullPage: true });
  });
});
