// @ts-check
const { test, expect } = require("@playwright/test");

// 設定測試的基礎 URL
const baseURL = "http://localhost:8001";

// 全域變數，用於在測試之間傳遞狀態
let downloadedTaskId = null;
let renamedFilename = "";

test.describe.configure({ mode: "serial" });

test.describe("綜合性端對端修復驗證", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(baseURL);
    // 等待頁面完全載入
    await page.waitForSelector("#app");
  });

  test("步驟 1: 媒體預覽 - 應能成功下載並預覽帶有特殊字元的影片", async ({
    page,
  }) => {
    // 導航到媒體下載器分頁
    await page.click('button[data-tab="downloader-tab"]');
    await expect(page.locator("#downloader-tab")).toBeVisible();

    // 使用模擬 URL 來確保測試的穩定性
    const videoUrl = "mock://video_with_special_chars";
    const videoTitle = "#貓meme 搞笑影片";

    // 使用 YouTube 處理流程來下載，因為它允許自訂檔名
    await page.click('button[data-tab="youtube-report-tab"]');
    await page.fill(".youtube-url-input", videoUrl);
    await page.fill(".youtube-filename-input", videoTitle);

    // 點擊「僅下載音訊」
    await page.click("#download-audio-only-btn");

    // 等待任務出現在「已完成」列表中
    const completedTaskSelector = `#completed-tasks .task-item:has-text("${videoTitle}")`;
    const taskElement = page.locator(completedTaskSelector);
    await expect(taskElement).toBeVisible({ timeout: 120000 }); // 增加超時以等待下載

    // 從「預覽」按鈕的 data-task-id 屬性中安全地提取 task-id
    const previewButtonForId = taskElement.locator(
      'a.btn-preview:has-text("預覽")',
    );
    downloadedTaskId = await previewButtonForId.getAttribute("data-task-id");
    expect(
      downloadedTaskId,
      "無法從預覽按鈕的 data-task-id 屬性中提取 task-id",
    ).toBeTruthy();
    console.log(`擷取到的下載任務 ID: ${downloadedTaskId}`);

    // 點擊「預覽」按鈕，使用精確的定位器
    const previewButton = taskElement.locator('a.btn-preview:has-text("預覽")');
    await expect(previewButton).toBeVisible();
    await previewButton.click();

    // 驗證預覽彈出視窗是否可見
    const modal = page.locator("#preview-modal");
    await expect(modal).toBeVisible();

    // 驗證彈出視窗中的音訊播放器是否已載入且沒有錯誤
    const audioPlayer = modal.locator("audio");
    await expect(audioPlayer).toBeVisible();

    // 透過評估 audio 元素的 networkState 來確認媒體是否載入成功
    // NETWORK_IDLE (1) 表示瀏覽器已完成媒體資源的載入
    await expect(audioPlayer).toHaveJSProperty("networkState", 1, {
      timeout: 15000,
    });

    // 關閉預覽彈出視窗
    await modal.locator("#modal-close-btn").click();
    await expect(modal).not.toBeVisible();
  });

  test("步驟 2: Gemini 模型 - 應能成功載入模型列表", async ({ page }) => {
    // 確保我們在 YouTube 分頁
    await page.click('button[data-tab="youtube-report-tab"]');

    // 從環境變數中獲取 API 金鑰
    const apiKey = process.env.TEST_GEMINI_API_KEY;
    expect(apiKey, "測試用的 TEST_GEMINI_API_KEY 環境變數未設定").toBeTruthy();

    // 輸入並儲存金鑰
    await page.fill("#api-key-input", apiKey);
    await page.click("#save-api-key-btn");

    // 驗證金鑰狀態是否變為有效
    await expect(page.locator("#api-key-status")).toContainText("金鑰有效", {
      timeout: 15000,
    });

    // 驗證模型下拉選單是否成功載入
    const modelSelect = page.locator("#gemini-model-select");
    // 等待第一個選項出現，並確保它不是錯誤訊息
    await expect(modelSelect.locator("option").first()).not.toContainText(
      "載入失敗",
      { timeout: 15000 },
    );
    await expect(modelSelect.locator("option").first()).not.toContainText(
      "等待從伺服器載入",
      { timeout: 15000 },
    );

    // 斷言至少有一個模型被載入
    const optionCount = await modelSelect.locator("option").count();
    expect(optionCount).toBeGreaterThan(0);
  });

  test("步驟 3: 檔案重新命名 - 應能成功重新命名已下載的檔案", async ({
    page,
  }) => {
    expect(
      downloadedTaskId,
      "前一個測試未成功設定 downloadedTaskId",
    ).not.toBeNull();

    // 重新導航到包含已完成任務的頁面，確保狀態一致
    await page.click('button[data-tab="youtube-report-tab"]');

    const taskElement = page.locator(
      `#completed-tasks .task-item:has-text("#貓meme 搞笑影片")`,
    );
    await expect(taskElement).toBeVisible();

    // 點擊重新命名按鈕
    const renameButton = taskElement.locator("a.btn-rename");
    await expect(renameButton).toBeVisible();

    renamedFilename = `重新命名後的貓咪影片 ${new Date().getTime()}`;

    // 監聽 prompt 對話框
    page.on("dialog", async (dialog) => {
      expect(dialog.type()).toContain("prompt");
      await dialog.accept(renamedFilename);
    });

    await renameButton.click();

    // 驗證 UI 更新：新的檔名應該出現
    const newFilenameSelector = `#completed-tasks .task-item:has-text("${renamedFilename}")`;
    await expect(page.locator(newFilenameSelector)).toBeVisible({
      timeout: 10000,
    });

    // 驗證舊的檔名已不存在
    await expect(
      page.locator(`#completed-tasks .task-item:has-text("#貓meme 搞笑影片")`),
    ).not.toBeVisible();
  });
});
