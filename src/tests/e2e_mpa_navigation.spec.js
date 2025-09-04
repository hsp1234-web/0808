// @ts-check
import { test, expect } from "@playwright/test";

test.describe("MPA v2 Navigation", () => {
  test("should navigate to all v2 pages and check titles", async ({ page }) => {
    // 1. Start at the root, which should be the index page
    await page.goto("/");
    await expect(page).toHaveTitle(/主儀表板/);
    await expect(page.locator("a.tab-button.active")).toHaveText("🏠 主儀表板");

    // 2. Navigate to Transcribe page
    await page.getByRole("link", { name: "📁 本機檔案轉錄" }).click();
    await expect(page).toHaveURL(/transcribe_v2.html/);
    await expect(page).toHaveTitle(/本機檔案轉錄/);
    await expect(page.locator("a.tab-button.active")).toHaveText(
      "📁 本機檔案轉錄",
    );
    await expect(page.locator("#local-file-tab")).toBeVisible();

    // 3. Navigate to Downloader page
    await page.getByRole("link", { name: "📥 媒體下載器" }).click();
    await expect(page).toHaveURL(/downloader_v2.html/);
    await expect(page).toHaveTitle(/媒體下載器/);
    await expect(page.locator("a.tab-button.active")).toHaveText(
      "📥 媒體下載器",
    );
    await expect(page.locator("#downloader-tab")).toBeVisible();

    // 4. Navigate to YouTube Report page
    await page.getByRole("link", { name: "▶️ YouTube 轉報告" }).click();
    await expect(page).toHaveURL(/youtube_report_v2.html/);
    await expect(page).toHaveTitle(/YouTube 轉報告/);
    await expect(page.locator("a.tab-button.active")).toHaveText(
      "▶️ YouTube 轉報告",
    );
    await expect(page.locator("#youtube-report-tab")).toBeVisible();

    // 5. Navigate to Prompts page
    await page.getByRole("link", { name: "📝 提示詞管理" }).click();
    await expect(page).toHaveURL(/prompts_v2.html/);
    await expect(page).toHaveTitle(/提示詞管理/);
    // The prompts page doesn't have the main nav bar, but a back link
    await expect(page.locator("a.back-link")).toBeVisible();
    await expect(page.locator("a.back-link")).toHaveAttribute(
      "href",
      "index_v2.html",
    );

    // 6. Go back to the main page from prompts
    await page.locator("a.back-link").click();
    await expect(page).toHaveURL(/index_v2.html/);
    await expect(page).toHaveTitle(/主儀表板/);
  });
});
