const { test, expect } = require("@playwright/test");
const { spawn } = require("child_process");
const path = require("path");

// 從環境變數讀取 API 金鑰，確保安全性。
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
const API_MODE = process.env.API_MODE || "real"; // 預設為真實模式

if (!GOOGLE_API_KEY) {
  throw new Error("測試執行失敗：環境變數 'GOOGLE_API_KEY' 未被設定。");
}

const BILIBILI_URL = "https://b23.tv/xALqLQM";
// 根據 API_MODE 選擇要測試的模型名稱
const TARGET_MODEL_NAME_PARTIAL =
  API_MODE === "mock" ? "Gemini 1.5 Flash (模擬)" : "gemini-1.5-flash";

test.describe("E2E 處理流程測試", () => {
  let serverProcess;
  let serverReady = false;
  let serverUrl;

  test.beforeAll(async () => {
    const pythonPath = process.env.PYENV_ROOT
      ? `${process.env.PYENV_ROOT}/shims/python`
      : "python3";
    // 修正：執行正確的伺服器啟動腳本
    serverProcess = spawn(
      pythonPath,
      ["-u", "scripts/run_server_for_playwright.py"],
      {
        detached: true,
        env: {
          ...process.env,
          GOOGLE_API_KEY: GOOGLE_API_KEY,
          API_MODE: API_MODE,
        },
      },
    );

    // 修正：使用更穩健的 URL 解析和健康檢查
    serverProcess.stdout.on("data", (data) => {
      process.stdout.write(`[Orchestrator STDOUT]: ${data}`);
      const urlMatch = data.toString().match(/PROXY_URL:\s*(http:\/\/\S+)/);
      if (urlMatch && urlMatch[1]) {
        serverUrl = urlMatch[1].trim();
        console.log(`[Test] 偵測到伺服器 URL: ${serverUrl}`);
      }
    });

    serverProcess.stderr.on("data", (data) => {
      process.stderr.write(`[Orchestrator STDERR]: ${data}`);
    });

    const startTime = Date.now();
    while (Date.now() - startTime < 60000) {
      if (serverUrl) {
        try {
          const response = await fetch(`${serverUrl}/api/health`);
          if (response.status === 200) {
            console.log("[Test] ✅ 健康檢查成功，伺服器已就緒。");
            serverReady = true;
            break;
          }
        } catch (e) {
          /* ignore */
        }
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    if (!serverReady) {
      throw new Error("伺服器在 60 秒內未能啟動或通過健康檢查。");
    }
  });

  test.afterAll(() => {
    if (serverProcess) {
      console.log("正在終止伺服器進程...");
      serverProcess.kill("SIGINT");
    }
  });

  test("應能成功處理一個 Bilibili 影片並驗證報告功能", async ({ page }) => {
    await page.goto(serverUrl);
    await page.getByTestId("youtube-report-tab").click();
    await expect(page.locator("#youtube-report-tab.tab-content")).toBeVisible();

    // 設定 API 金鑰並載入模型
    await page.getByTestId("api-key-input").fill(GOOGLE_API_KEY);
    await page.getByTestId("save-api-key-button").click();
    await expect(page.getByText("模型載入成功")).toBeVisible({
      timeout: 20000,
    });

    // 選擇指定的模型
    const modelSelect = page.getByTestId("gemini-model-select");
    await expect(
      modelSelect.locator("option", { hasText: "等待從伺服器載入模型列表..." }),
    ).toHaveCount(0, { timeout: 10000 });

    const options = await modelSelect.locator("option").all();
    let targetOptionValue;
    for (const option of options) {
      const text = await option.textContent();
      if (
        text.toLowerCase().includes(TARGET_MODEL_NAME_PARTIAL.toLowerCase())
      ) {
        targetOptionValue = await option.getAttribute("value");
        break;
      }
    }
    if (!targetOptionValue) {
      throw new Error(`找不到包含 "${TARGET_MODEL_NAME_PARTIAL}" 的模型選項`);
    }
    await modelSelect.selectOption({ value: targetOptionValue });

    // 新增並處理 Bilibili 任務
    await page.getByTestId("add-youtube-row-button").click();
    await page.locator(".youtube-url-input").nth(0).fill(BILIBILI_URL);
    await page.getByTestId("start-youtube-processing-button").click();

    // 等待最終報告項目出現
    const reportItem = page
      .locator("#youtube-file-browser .task-item")
      .filter({ hasText: /模擬影片標題|十年了/ });
    await expect(reportItem).toBeVisible({ timeout: 240000 });
    console.log("[Test] 在報告瀏覽區找到已完成的項目。");

    // 驗證「詳細資訊」功能
    const detailsButton = reportItem.locator('a:has-text("詳細資料")');
    await detailsButton.click();
    await expect(page.getByTestId("task-detail-modal")).toBeVisible();
    await expect(page.getByTestId("task-detail-content")).toContainText(
      /總 Token 消耗/,
    );
    await page.getByTestId("task-detail-close-button").click();
    await expect(page.getByTestId("task-detail-modal")).not.toBeVisible();
    console.log("[Test] ✅ 詳細資訊功能驗證成功。");

    // 驗證「預覽報告」功能
    await reportItem.getByTestId("view-report-button").click();
    await expect(page.getByTestId("report-modal")).toBeVisible();
    const iframe = page.frameLocator("#preview-modal iframe");
    await expect(iframe.locator("body")).toContainText(/AI (學習|分析)報告/, {
      timeout: 15000,
    });
    console.log("[Test] ✅ 預覽報告功能驗證成功。");

    // 截圖驗證
    await page.screenshot({ path: "e2e-final-state.png", fullPage: true });
  });
});
