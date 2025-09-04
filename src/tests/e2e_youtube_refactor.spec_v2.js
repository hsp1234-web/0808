import { test, expect } from "@playwright/test";

test.describe("YouTube Refactor E2E Test", () => {
  test("should run the new YouTube to Report workflow and produce a .txt file", async ({
    page,
  }) => {
    // 1. Go to the page
    await page.goto("/");

    // 2. Click the "YouTube 轉報告" tab
    await page.getByRole("button", { name: "▶️ YouTube 轉報告" }).click();
    await expect(page.locator("#youtube-report-tab")).toBeVisible();

    // 3. Enter and validate a mock API key
    await page.locator("#api-key-input").fill("mock-api-key");
    await page.getByRole("button", { name: "儲存金鑰" }).click();
    await expect(page.locator("#api-key-status")).toContainText("金鑰有效");
    await expect(page.locator("#youtube-params-fieldset")).toBeEnabled();

    // 4. Enter a YouTube URL
    const MOCK_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
    await page.locator(".youtube-url-input").fill(MOCK_URL);

    // 5. Uncheck "詳細逐字稿" and check "翻譯", leaving "重點摘要" checked.
    await page.locator('input[name="yt-task"][value="transcript"]').uncheck();
    await page.locator('input[name="yt-task"][value="translate"]').check();

    // Verify checkbox states
    await expect(
      page.locator('input[name="yt-task"][value="summary"]'),
    ).toBeChecked();
    await expect(
      page.locator('input[name="yt-task"][value="transcript"]'),
    ).not.toBeChecked();
    await expect(
      page.locator('input[name="yt-task"][value="translate"]'),
    ).toBeChecked();

    // 6. Select "純文字 (.txt)" from the output format dropdown
    await page.locator("#yt-output-format-select").selectOption("txt");

    // 7. Click the "Analyze" button
    await page.getByRole("button", { name: "🚀 分析影片 (Gemini)" }).click();

    // 8. Wait for the task to appear in the YouTube report browser list
    const completedTask = page.locator("#youtube-file-browser .task-item");
    await expect(completedTask.first()).toBeVisible({ timeout: 30000 });

    // Check that the task text contains the video title
    const MOCK_TITLE = `'${MOCK_URL}' 的模擬影片標題`;
    const completedTaskText = await completedTask.first().textContent();
    expect(completedTaskText).toContain(MOCK_TITLE);

    // Check for the download button to have the correct .txt extension
    const downloadLink = completedTask.first().locator("a.btn-download");
    await expect(downloadLink).toHaveAttribute("download", /_report\.txt$/);

    // 9. Take a screenshot
    await page.screenshot({
      path: "tests/e2e_youtube_refactor_screenshot.png",
    });
  });
});
