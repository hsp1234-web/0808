// @ts-check
const { test, expect } = require("@playwright/test");

// 使用者提供的金鑰和測試參數
const USER_API_KEY = "AIzaSyCR4gdpWDk9evli0iULcfkiOinL_vKdFnU";
const YOUTUBE_URL =
  "https://youtube.com/shorts/mG5z-pfhIiA?si=rIHZPsD_VpbgGeFt";
const BILIBILI_URL = "https://b23.tv/xALqLQM";
const TARGET_MODEL_NAME = "Gemini 2.5 Flash-Lite Preview 06-17"; // 根據使用者要求
const TARGET_MODEL_ID = "models/gemini-1.5-flash-latest"; // 這通常是 UI 顯示名稱對應的後端 ID

test.describe("完整 YouTube 報告生成流程測試", () => {
  test.beforeEach(async ({ page }) => {
    // 每次測試前都先導航到主頁面
    await page.goto("/");
    // 清理資料庫，確保測試環境乾淨
    const response = await page.request.post("/api/debug/clear_tasks");
    await expect(response.ok()).toBeTruthy();
    // 等待核心系統就緒
    await expect(page.locator("#status-text")).toHaveText("已連線", {
      timeout: 30000,
    });
  });

  test("應能成功處理多個 URL、驗證所有 UI 元素並產生報告", async ({ page }) => {
    // 設定一個較長的超時時間，因為整個流程（下載、轉錄、AI分析）可能需要數分鐘
    test.setTimeout(5 * 60 * 1000); // 5 分鐘

    // --- 1. 切換到 "YouTube 轉報告" 分頁 ---
    await page.getByRole("button", { name: "▶️ YouTube 轉報告" }).click();
    await expect(page.locator("#youtube-report-tab")).toBeVisible();

    // --- 2. 設定 API 金鑰和模型 ---
    await page
      .getByPlaceholder("在此貼上您的 Google API 金鑰")
      .fill(USER_API_KEY);
    await page.getByRole("button", { name: "儲存金鑰" }).click();

    // 等待金鑰驗證成功並載入模型列表
    await expect(page.locator("#api-key-status > span")).toHaveText(
      "金鑰有效，Gemini 功能已啟用",
      { timeout: 20000 },
    );
    await expect(page.locator("#gemini-model-select")).toBeEnabled({
      timeout: 10000,
    });

    // 選擇指定的 Gemini 模型
    // 注意：這裡我們選擇的是顯示名稱，Playwright 會自動找到對應的 <option>
    await page
      .locator("#gemini-model-select")
      .selectOption({ label: TARGET_MODEL_NAME });

    // --- 3. 輸入網址 ---
    await page.getByPlaceholder("YouTube 影片網址").first().fill(YOUTUBE_URL);
    await page.getByRole("button", { name: "+ 新增一列" }).click();
    await page.getByPlaceholder("YouTube 影片網址").last().fill(BILIBILI_URL);

    // --- 4. 設定處理參數 ---
    // 勾選所有任務選項
    await page.getByLabel("重點摘要").check();
    await page.getByLabel("詳細逐字稿").check();
    await page.getByLabel("使用原文 (基於逐字稿)").check();
    await page.getByLabel("翻譯成繁體中文 (基於逐字稿)").check();

    // 選擇輸出格式為 HTML
    await page
      .locator("#yt-output-format-select")
      .selectOption({ label: "HTML 報告" });

    // --- 5. 開始處理並驗證「處理中」狀態 ---
    await page.getByRole("button", { name: "🚀 分析影片 (Gemini)" }).click();

    // 驗證我們提交的兩個URL都已出現在「處理中任務」列表，這比檢查固定數量更可靠
    const ongoingTasksContainer = page.locator("#ongoing-tasks");
    // JULES'S FIX (V2): Use .first() to handle multiple tasks created for a single URL, satisfying strict mode.
    await expect(
      ongoingTasksContainer
        .locator(".task-filename")
        .getByText(/mG5z-pfhIiA/)
        .first(),
    ).toBeVisible({ timeout: 20000 });
    await expect(
      ongoingTasksContainer
        .locator(".task-filename")
        .getByText(/xALqLQM/)
        .first(),
    ).toBeVisible({ timeout: 20000 });

    // 驗證狀態文字包含「處理中」
    // 這裡我們只驗證第一個任務的狀態，作為代表
    await expect(
      ongoingTasksContainer.locator(".task-item .task-status").first(),
    ).toContainText("處理中", { timeout: 20000 });

    // --- 6. 等待任務完成並驗證結果 ---
    const reportBrowser = page.locator("#youtube-file-browser");

    // 等待報告出現在瀏覽區，給予足夠長的超時時間
    await expect(reportBrowser.locator(".task-item")).toHaveCount(2, {
      timeout: 4 * 60 * 1000,
    });

    // --- 7. 驗證報告 UI 元素與功能 ---
    const firstReport = reportBrowser.locator(".task-item").first();
    const secondReport = reportBrowser.locator(".task-item").last();

    // 驗證兩個報告的標題都已出現
    await expect(firstReport.getByText(/mG5z-pfhIiA/i)).toBeVisible(); // 用 URL 的一部分來識別
    await expect(secondReport.getByText(/xALqLQM/i)).toBeVisible(); // 用 URL 的一部分來識別

    // 對第一個報告進行詳細驗證
    await expect(
      firstReport.getByRole("link", { name: "詳細資料" }),
    ).toBeVisible();
    await expect(firstReport.getByRole("link", { name: "預覽" })).toBeVisible();
    await expect(firstReport.getByRole("link", { name: "下載" })).toBeVisible();
    // 根據使用者的要求，也檢查「重新命名」按鈕是否存在
    // 注意：如果此功能未實作，此斷言將會失敗，屆時再根據情況調整
    await expect(
      firstReport.getByRole("link", { name: "修改名稱" }),
    ).toBeVisible();

    // 測試「詳細資料」彈窗
    await firstReport.getByRole("link", { name: "詳細資料" }).click();
    const detailsModal = page.locator("#details-modal");
    await expect(detailsModal).toBeVisible();
    await expect(detailsModal.getByText("總 Token 消耗:")).toBeVisible();
    await expect(detailsModal.getByText("總執行時間:")).toBeVisible();
    await detailsModal.getByRole("button", { name: "確認" }).click();
    await expect(detailsModal).not.toBeVisible();

    // 測試「預覽」彈窗
    await firstReport.getByRole("link", { name: "預覽" }).click();
    const previewModal = page.locator("#preview-modal");
    await expect(previewModal).toBeVisible();
    // 驗證 iframe 是否存在，表示 HTML 報告正在被載入
    await expect(previewModal.locator("iframe")).toBeVisible();
    await previewModal.locator("#modal-close-btn").click();
    await expect(previewModal).not.toBeVisible();

    // --- 8. 產生最終截圖 ---
    await page.screenshot({
      path: "e2e_youtube_report_full_success.jpg",
      fullPage: true,
    });

    // 測試全部通過的最終斷言
    await expect(page.locator("#no-ongoing-task-msg")).toBeVisible({
      timeout: 10000,
    });
  });
});
