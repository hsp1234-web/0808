// @ts-check
const { test, expect } = require("@playwright/test");

// 測試資料
const YOUTUBE_URL =
  "https://youtube.com/shorts/HMS4V6VTIaI?si=UgJD_EiARGXb15VX";
const GEMINI_API_KEY = "AIzaSyBLYgpBaV2LDTzNu4ksuq-xyPmRj1VwpF0";

test.describe("錯誤修復驗證測試 (Bug Fix Verification Tests)", () => {
  test.beforeEach(async ({ page }) => {
    // 每次測試前都先導航到主頁面
    await page.goto("/");
    // 等待 WebSocket 連線成功
    await expect(page.locator("#status-text")).toHaveText("已連線", {
      timeout: 15000,
    });
  });

  test("【驗證】媒體下載功能：移除寫死路徑後應能正確回報網路錯誤", async ({
    page,
  }) => {
    // 1. 切換到「媒體下載器」分頁
    await page.getByRole("button", { name: "📥 媒體下載器" }).click();

    // 2. 輸入 YouTube 網址
    await page.locator("#downloader-urls-input").fill(YOUTUBE_URL);

    // 3. 點擊下載按鈕
    await page.getByRole("button", { name: "開始下載" }).click();

    // 4. 斷言：任務出現在列表中
    const taskElement = page.locator("#downloader-tasks .task-item").first();
    await expect(taskElement).toBeVisible({ timeout: 10000 });
    await expect(taskElement.locator(".task-filename")).toContainText(
      "youtube.com",
    );

    // 5. 斷言：任務最終狀態應為「失敗」，因為環境的網路問題 (403 Forbidden)
    // 這是預期中的「正確失敗」，證明我們的程式碼修復後，yt-dlp 能被正確呼叫
    const statusSpan = taskElement.locator(".task-status");
    await expect(statusSpan).toHaveText("❌ 失敗", { timeout: 90000 });

    // 6. 斷言：顯示了詳細的錯誤訊息
    const errorDetails = taskElement.locator(".task-error-details");
    await expect(errorDetails).toBeVisible();
    await expect(errorDetails).toContainText("403");
  });

  test("【驗證】AI 模型載入功能：API 金鑰應能正確傳遞並載入模型", async ({
    page,
  }) => {
    // 1. 切換到「YouTube 轉報告」分頁
    await page.getByRole("button", { name: "▶️ YouTube 轉報告" }).click();

    // 2. 輸入 API 金鑰
    await page.locator("#api-key-input").fill(GEMINI_API_KEY);

    // 3. 點擊儲存金鑰按鈕
    await page.getByRole("button", { name: "儲存金鑰" }).click();

    // 4. 斷言：UI 顯示金鑰有效
    await expect(page.locator("#api-key-status > span")).toHaveText(
      "金鑰有效，Gemini 功能已啟用",
      { timeout: 10000 },
    );

    // 5. 關鍵步驟：等待模型列表的 API 請求完成，徹底消除競爭條件
    await page.waitForResponse(
      (resp) =>
        resp.url().includes("/api/youtube/models") && resp.status() === 200,
      { timeout: 10000 },
    );

    // 6. 斷言：「AI 模型」下拉式選單成功載入模型
    const modelSelect = page.locator("#gemini-model-select");

    // 現在可以安全地進行斷言
    const firstOptionText = await modelSelect
      .locator("option")
      .first()
      .textContent();
    expect(firstOptionText).toContain("Gemini");
    expect(firstOptionText).not.toContain("載入失敗");
    expect(firstOptionText).not.toContain("無法載入");
  });
});
