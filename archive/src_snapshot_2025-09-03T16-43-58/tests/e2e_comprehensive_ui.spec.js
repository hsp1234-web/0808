// @ts-check
import { test, expect } from "@playwright/test";
import path from "path";

/**
 * @file 該檔案為 `mp3.html` 頁面的全功能、綜合性端對端 (E2E) 測試。
 * @description 此測試套件的目的是模擬使用者在所有主要功能區塊的完整操作流程，
 *              以確保在進行大型架構重構（如 SPA -> MPA）時，所有功能保持正確。
 *              測試包含了 UI 互動、狀態驗證、模擬檔案處理以及為每個主要分頁產生截圖。
 *
 * @tech-stack Playwright
 * @author Jules
 */

// --- 測試設定 ---
const SERVER_URL = "http://127.0.0.1:42649/"; // 來自 `run_server_for_playwright.py` 的埠號
const TEST_TIMEOUT = 120000; // 為這個複雜的測試設定更長的超時時間 (120 秒)

// --- E2E 測試套件 ---
test.describe("綜合性 UI 功能測試: mp3.html", () => {
  test.setTimeout(TEST_TIMEOUT);

  // 在所有測試開始前，導覽至頁面並等待基礎 UI 就緒
  test.beforeEach(async ({ page }) => {
    // JULES'S FINAL FIX (2025-09-02): 在每次測試前呼叫後端 API 來清除所有任務。
    // 這是解決測試間狀態污染的關鍵，確保每個測試都在乾淨的環境中開始。
    await page.request.post(`${SERVER_URL}api/debug/clear_tasks`);

    await page.goto(SERVER_URL, { waitUntil: "domcontentloaded" });
    // 等待 WebSocket 連線成功，這是頁面就緒的關鍵指標
    await expect(page.locator("#status-text")).toContainText("已連線", {
      timeout: 20000,
    });
  });

  // --- 測試案例 1: 「本機檔案轉錄」分頁 ---
  test.describe("「本機檔案轉錄」分頁功能測試", () => {
    test("應能成功上傳檔案並擷取分頁截圖", async ({ page }) => {
      // 1. 點擊「本機檔案轉錄」分頁 (雖然預設是開啟的，但點擊可確保測試的獨立性)
      // API 端點註解: 此處為純前端互動，不涉及後端 API 呼叫
      await page.locator('button[data-tab="local-file-tab"]').click();

      // 2. 與 UI 控制項互動
      // API 端點註解: 更改這些選項會更新前端狀態，在提交時可能會透過 /api/log/action 記錄，但核心互動是前端的。
      await page.locator("#model-select").selectOption("base");
      await expect(page.locator("#model-display")).toHaveText("base");

      // 3. 模擬檔案上傳
      // API 端點註解: 此操作將檔案載入到瀏覽器記憶體中，準備後續發送到 /api/transcribe 端點。
      const fileInput = page.locator("#file-input");
      const mockFilePath = path.join(process.cwd(), "mock_upload.txt");
      await fileInput.setInputFiles(mockFilePath);

      // 4. 驗證 UI 反應
      // 驗證檔案是否出現在待處理列表中
      await expect(page.locator("#file-list")).toContainText("mock_upload.txt");
      // 驗證「開始處理」按鈕是否已啟用
      const startBtn = page.locator("#start-processing-btn");
      await expect(startBtn).toBeEnabled();
      await expect(startBtn).toContainText("開始處理 1 個檔案");

      // 5. 點擊開始處理
      // API 端點註解: 此點擊會觸發 POST 到 /api/transcribe，並透過 WebSocket 開始接收進度更新
      await startBtn.click();
      const ongoingTask = page.locator("#ongoing-tasks .task-item");
      await expect(ongoingTask).toContainText("mock_upload.txt");
      await page.screenshot({
        path: "mpa_design_references/01_local_file_task_created.jpg",
        fullPage: true,
      });

      // 6. 等待任務完成並驗證
      const completedTask = page.locator("#completed-tasks .task-item");
      await expect(completedTask).toContainText("mock_upload.txt", {
        timeout: 15000,
      });
      await expect(ongoingTask).not.toBeVisible(); // 驗證任務已從處理中列表移除
      await page.screenshot({
        path: "mpa_design_references/02_local_file_task_completed.jpg",
        fullPage: true,
      });

      // 7. 驗證預覽功能
      // API 端點註解: 預覽按鈕會讀取任務結果中的 output_path，並在前端開啟一個 Modal 來顯示內容，不直接呼叫後端 API。
      const previewBtn = completedTask.locator(
        '[data-testid="view-report-button"]',
      );
      await previewBtn.click();
      const previewModal = page.locator("#preview-modal");
      await expect(previewModal).toBeVisible();
      // 驗證 Modal 內的內容 (mock server 應回傳特定文字)
      await expect(previewModal.locator(".modal-body pre")).toContainText(
        "這是模擬的轉錄稿內容",
      );
      await page.screenshot({
        path: "mpa_design_references/03_local_file_preview_modal.jpg",
        fullPage: true,
      });
    });
  });

  // --- 測試案例 2: 「媒體下載器」分頁 ---
  test.describe("「媒體下載器」分頁功能測試", () => {
    test("應能成功提交下載任務並擷取分頁截圖", async ({ page }) => {
      // 1. 點擊「媒體下載器」分頁
      // API 端點註解: 純前端互動
      await page.locator('button[data-tab="downloader-tab"]').click();

      // 2. 填寫表單並與控制項互動
      // API 端點註解: 這些互動是前端行為，最終點擊按鈕時會將這些狀態發送到 /api/youtube/process
      const mockUrl = "https://www.youtube.com/watch?v=mock_video_id";
      await page.locator("#downloader-urls-input").fill(mockUrl);
      await page.locator('input[name="download-type"][value="video"]').check();
      // 等待影片選項可見
      await expect(page.locator("#video-options")).toBeVisible();
      await page.locator("#video-quality-select").selectOption("720p");

      // 3. 提交下載任務
      // API 端點註解: 此點擊會觸發一個 POST 請求到 /api/youtube/process 端點
      await page.locator("#start-download-btn").click();

      // 4. 驗證 UI 反應
      // 驗證下載佇列中出現了新任務
      const taskItem = page.locator("#downloader-tasks .task-item").first(); // Use first() to be specific
      await expect(taskItem).toBeVisible({ timeout: 10000 });
      await expect(taskItem).toContainText(mockUrl);
      await expect(taskItem).toContainText("僅下載影片");
      await page.screenshot({
        path: "mpa_design_references/04_downloader_task_created.jpg",
        fullPage: true,
      });

      // 5. 等待任務完成並驗證
      // Mock server 應該很快完成這個任務
      await expect(
        taskItem.locator('[data-testid="view-report-button"]'),
      ).toBeVisible({ timeout: 15000 });
      await expect(taskItem).toContainText("已完成"); // 驗證狀態文字
      await page.screenshot({
        path: "mpa_design_references/05_downloader_task_completed.jpg",
        fullPage: true,
      });
    });
  });

  // --- 測試案例 3: 「YouTube 轉報告」分頁 ---
  test.describe("「YouTube 轉報告」分頁功能測試", () => {
    test("應能成功儲存 API Key、提交分析任務、並擷取分頁截圖", async ({
      page,
    }) => {
      // 1. 點擊「YouTube 轉報告」分頁
      // API 端點註解: 純前端互動
      await page.locator('button[data-tab="youtube-report-tab"]').click();

      // 2. 測試 API 金鑰管理
      // API 端點註解: 儲存金鑰會觸發 POST 到 /api/youtube/models 來驗證金鑰並獲取模型列表
      const apiKeyInput = page.locator('[data-testid="api-key-input"]');
      const saveApiKeyBtn = page.locator('[data-testid="save-api-key-button"]');
      const apiKeyStatus = page.locator("#api-key-status");

      await apiKeyInput.fill("DUMMY_KEY_FOR_TEST");
      await saveApiKeyBtn.click();
      // 驗證金鑰狀態是否更新為成功 (mock server 應回傳成功)
      await expect(apiKeyStatus).toContainText("金鑰有效", { timeout: 10000 });
      // 驗證模型下拉選單是否被填充，並檢查其預設選定值
      await expect(
        page.locator('[data-testid="gemini-model-select"]'),
      ).toHaveValue("gemini-pro-mock");

      // 3. 填寫表單並提交任務
      const mockUrl = "https://www.youtube.com/watch?v=final_mock_video";
      await page.locator(".youtube-url-input").fill(mockUrl);
      await page
        .locator('[data-testid="start-youtube-processing-button"]')
        .click();

      // 4. 驗證 UI 反應
      // 4. 驗證 UI 反應
      const ongoingTask = page.locator("#ongoing-tasks .task-item");
      await expect(ongoingTask).toBeVisible();
      await expect(ongoingTask).toContainText(mockUrl);
      await page.screenshot({
        path: "mpa_design_references/06_youtube_task_created.jpg",
        fullPage: true,
      });

      // 5. 等待任務完成並驗證
      const reportItem = page.locator("#youtube-file-browser .task-item");
      await expect(reportItem).toBeVisible({ timeout: 15000 });
      // JULES'S FIX (2025-09-02): 根據 mock_youtube_downloader.py 的實際輸出來修正斷言
      await expect(reportItem).toContainText("Mocked YouTube Video Title");
      await expect(ongoingTask).not.toBeVisible();
      await page.screenshot({
        path: "mpa_design_references/07_youtube_report_item.jpg",
        fullPage: true,
      });

      // 6. 驗證預覽功能
      const previewBtn = reportItem.locator(
        '[data-testid="view-report-button"]',
      );
      await previewBtn.click();
      const previewModal = page.locator("#preview-modal");
      await expect(previewModal).toBeVisible();
      // 驗證 Modal 內的 IFrame 是否已載入 (mock server 應回傳 html)
      const iframe = previewModal.frameLocator("iframe#report-iframe");
      // JULES'S FIX (2025-09-02): 根據 mock_gemini_processor.py 的實際輸出來修正斷言
      await expect(iframe.locator("body")).toContainText("AI 分析報告 (模擬)");
      await page.screenshot({
        path: "mpa_design_references/08_youtube_report_preview.jpg",
        fullPage: true,
      });
    });
  });
});
