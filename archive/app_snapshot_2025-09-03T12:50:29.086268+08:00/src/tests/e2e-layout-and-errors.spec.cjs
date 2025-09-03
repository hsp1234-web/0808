const { test, expect, devices } = require('@playwright/test');

test.describe('Layout and Error Handling Before Fixes', () => {
  // Mock data for the tests
  const MOCK_TASKS = [
    {
      task_id: 'task-1',
      type: 'transcribe',
      status: 'processing',
      payload: { original_filename: 'short-and-normal-file.wav' },
      result: null
    },
    {
      task_id: 'task-2',
      type: 'transcribe',
      status: 'processing',
      payload: { original_filename: 'this-is-a-very-very-very-long-filename-that-is-designed-to-break-the-layout-of-the-task-list-and-test-the-ellipsis-feature.mp3' },
      result: null
    },
    {
        task_id: 'task-3',
        type: 'transcribe',
        status: 'completed',
        payload: { original_filename: 'a-completed-task.mp3'},
        result: { output_path: '/media/some-file.mp3' }
    }
  ];

  const MOCK_500_ERROR = {
    detail: "500 An internal error has occurred. Please retry or report in https://developers.generativeai.google/guide/troubleshooting"
  };

  // This setup runs before each test.
  test.beforeEach(async ({ page }) => {
    // Mock the API endpoint to get tasks
    await page.route('**/api/tasks', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_TASKS),
      });
    });

    // Mock the API endpoint that will trigger a 500 error
    await page.route('**/api/youtube/process', route => {
        route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify(MOCK_500_ERROR),
        });
    });

    // Mock other non-essential endpoints to prevent console errors
    await page.route('**/api/app_state', route => route.fulfill({ status: 200, json: {} }));
    await page.route('**/api/system/readiness', route => route.fulfill({ status: 200, json: { ready: true } }));
    await page.route('**/api/system_stats', route => route.fulfill({ status: 200, json: { cpu_usage: 10, ram_usage: 50, gpu_detected: false } }));
  });

  test('should capture layout issues on Desktop', async ({ page }) => {
    await page.goto('/');

    // Trigger the 500 error
    await page.getByTestId('youtube-report-tab').click();
    // FIX: Fill the input to pass frontend validation before clicking
    await page.locator('.youtube-url-input').fill('https://dummy.url/for/testing');
    await page.getByTestId('start-youtube-processing-button').click({ force: true }); // Force click as it might be disabled

    // Wait for the tasks to be visible
    await expect(page.locator('.task-item').nth(1)).toBeVisible();

    // Take a screenshot of the initial state
    await page.screenshot({ path: 'after-desktop.jpg', fullPage: true });
  });

  test('should capture layout issues on Mobile', async ({ browser }) => {
    // Emulate a Google Pixel 5, which is a good representation of a 6-inch phone
    const context = await browser.newContext({
        ...devices['Pixel 5'],
    });
    const page = await context.newPage();

    // Have to re-apply routes for the new page context
    await page.route('**/api/tasks', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TASKS) }));
    await page.route('**/api/youtube/process', route => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify(MOCK_500_ERROR) }));
    await page.route('**/api/app_state', route => route.fulfill({ status: 200, json: {} }));
    await page.route('**/api/system/readiness', route => route.fulfill({ status: 200, json: { ready: true } }));
    await page.route('**/api/system_stats', route => route.fulfill({ status: 200, json: { cpu_usage: 10, ram_usage: 50, gpu_detected: false } }));

    await page.goto('/');

    // Trigger the 500 error
    await page.getByTestId('youtube-report-tab').click();
    // FIX: Fill the input to pass frontend validation before clicking
    await page.locator('.youtube-url-input').fill('https://dummy.url/for/testing');
    await page.getByTestId('start-youtube-processing-button').click({ force: true });

    // Wait for elements to be visible
    await expect(page.locator('.task-item').nth(1)).toBeVisible();

    // Take a screenshot of the initial state on mobile
    await page.screenshot({ path: 'after-mobile.jpg', fullPage: true });

    await context.close();
  });
});
