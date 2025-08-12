import { test, expect } from '@playwright/test';

test.describe('Prompts Page E2E Test', () => {
  const serverUrl = 'http://127.0.0.1:42649';

  test('should load, edit, save, and reload prompts', async ({ page }) => {
    // 1. Navigate to the prompts page
    await page.goto(`${serverUrl}/static/prompts.html`);

    // 2. Check that the a default prompt label is visible
    await expect(page.getByText('get_summary_only')).toBeVisible();

    const promptTextarea = page.locator('textarea[name="get_summary_only"]');
    await expect(promptTextarea).toBeVisible();

    // 3. Edit the prompt
    const newPromptText = 'This is a new test prompt for get_summary_only.';
    await promptTextarea.fill(newPromptText);

    // 4. Click Save
    await page.getByRole('button', { name: '儲存變更' }).click();

    // 5. Wait for success message
    const statusMessage = page.locator('#status-area');
    await expect(statusMessage).toContainText('提示詞已成功更新。');
    await expect(statusMessage).toHaveClass(/success/);

    // 6. Reload the page
    await page.reload();

    // 7. Check that the new prompt text is still there
    await expect(page.getByText('get_summary_only')).toBeVisible();
    const reloadedPromptTextarea = page.locator('textarea[name="get_summary_only"]');
    await expect(reloadedPromptTextarea).toHaveValue(newPromptText);

    // 8. Take a screenshot
    await page.screenshot({ path: 'tests/e2e_prompts_page_screenshot.png' });
  });
});
