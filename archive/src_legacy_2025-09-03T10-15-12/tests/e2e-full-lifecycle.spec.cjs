const { test, expect } = require("@playwright/test");

test.describe("Full Task Lifecycle E2E Test", () => {
  let serverUrl;

  test.beforeEach(async ({ page }) => {
    // --- Mock API Endpoints ---

    // Mock initial tasks to be empty
    await page.route("**/api/tasks", (route) => {
      route.fulfill({ status: 200, json: [] });
    });

    // Mock system stats to ensure dashboard loads
    await page.route("**/api/system_stats", (route) => {
      route.fulfill({
        status: 200,
        json: {
          cpu_usage: 15.5,
          ram_usage: 55.2,
          gpu_detected: true,
          gpu_usage: 25.8,
        },
      });
    });

    // Mock other non-essential endpoints
    await page.route("**/api/app_state", (route) =>
      route.fulfill({ status: 200, json: {} }),
    );
    await page.route("**/api/system/readiness", (route) =>
      route.fulfill({ status: 200, json: { ready: true } }),
    );
    await page.route("**/api/log/action", (route) =>
      route.fulfill({ status: 200 }),
    );

    // Mock the transcription creation endpoint
    await page.route("**/api/transcribe", async (route) => {
      const json = {
        task_id: "mock-task-123",
        type: "transcribe",
      };
      await route.fulfill({ status: 202, json });
    });

    await page.goto("/");
    serverUrl = page.url();
  });

  test("should correctly display dashboard, process a task, and show results with buttons", async ({
    page,
  }) => {
    // --- 1. Verify Dashboard ---
    await expect(page.locator("#cpu-label")).not.toContainText("--%", {
      timeout: 10000,
    });
    await expect(page.locator("#ram-label")).not.toContainText("--%", {
      timeout: 10000,
    });
    await expect(page.locator("#gpu-label")).not.toContainText("--%", {
      timeout: 10000,
    });
    await page.screenshot({
      path: "test-results/lifecycle-step1-dashboard-ok.jpg",
    });
    console.log("✅ [Test Step 1/5] Dashboard stats loaded correctly.");

    // --- 2. Start a Task ---
    // Use a real file for the upload to make the test more realistic
    const filePath = "src/tests/fixtures/test_audio.mp3";
    await page.setInputFiles("input#file-input", filePath);
    await expect(page.locator("#file-list .task-filename")).toContainText(
      "test_audio.mp3",
    );
    await page.getByRole("button", { name: /開始處理/ }).click();

    // --- 3. Verify Processing State ---
    // SIMPLIFICATION: Directly call the UI update function instead of mocking WebSockets
    await page.evaluate(() => {
      handleTranscriptionUpdate("TRANSCRIPTION_STATUS", {
        task_id: "mock-task-123",
        status: "starting",
        filename: "test_audio.mp3",
      });
    });

    const processingTaskItem = page.locator("#ongoing-tasks .task-item");
    await expect(processingTaskItem).toBeVisible({ timeout: 10000 });
    await expect(processingTaskItem).toContainText("test_audio.mp3");

    const timer = processingTaskItem.locator(".timer");
    // FIX: Combine visibility and text check to avoid race condition
    // where the timer span exists but is empty (and thus not "visible").
    await expect(timer).toContainText("經過時間: 0s", { timeout: 2000 });

    // Check that it updates
    await expect(timer).toContainText(/經過時間: [1-2]s/, { timeout: 2000 });
    await page.screenshot({
      path: "test-results/lifecycle-step2-processing-with-timer.jpg",
    });
    console.log("✅ [Test Step 2/5] Task is processing with a running timer.");

    // --- 4. Complete the Task ---
    const mockResult = {
      output_path: "/media/mock-results/test_audio.txt",
      transcript_path: "/media/mock-results/test_audio.txt",
      original_filename: "test_audio.mp3",
      html_report_path: null,
      txt_report_path: "/media/mock-results/test_audio.txt",
    };
    await page.evaluate((result) => {
      handleTranscriptionUpdate("TRANSCRIPTION_STATUS", {
        task_id: "mock-task-123",
        status: "completed",
        result: result,
      });
    }, mockResult);

    // --- 5. Verify Completed State ---
    const completedTaskItem = page.locator("#completed-tasks .task-item");
    await expect(completedTaskItem).toBeVisible({ timeout: 10000 });
    await expect(completedTaskItem).toContainText("test_audio.mp3");
    await expect(processingTaskItem).not.toBeVisible(); // Should be gone from processing list

    const previewButton = completedTaskItem.getByRole("link", { name: "預覽" });
    const downloadButton = completedTaskItem.getByRole("link", {
      name: "下載",
    });
    await expect(previewButton).toBeVisible();
    await expect(downloadButton).toBeVisible();
    await page.screenshot({
      path: "test-results/lifecycle-step3-completed-with-buttons.jpg",
    });
    console.log("✅ [Test Step 3/5] Task is completed with action buttons.");

    // --- 6. Verify Button Functionality ---
    // Mock the content for the preview
    await page.route("**/media/mock-results/test_audio.txt", (route) => {
      route.fulfill({
        status: 200,
        contentType: "text/plain",
        body: "This is the mock transcript content.",
      });
    });

    await previewButton.click();
    const modal = page.locator("#preview-modal");
    await expect(modal).toBeVisible();
    await expect(modal.locator(".modal-body pre")).toContainText(
      "This is the mock transcript content.",
    );
    await page.screenshot({
      path: "test-results/lifecycle-step4-preview-works.jpg",
    });
    console.log("✅ [Test Step 4/5] Preview button works correctly.");

    await modal.getByRole("button", { name: "×" }).click();
    await expect(modal).not.toBeVisible();
    console.log("✅ [Test Step 5/5] All steps verified successfully.");
  });
});
