import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/**
 * TaskList 元件測試套件
 */
test.describe('TaskList Component Tests', () => {

    let taskListCode;
    const baseURL = 'http://127.0.0.1:42649'; // 必須與 playwright.config.js 中一致

    // 在所有測試執行前，讀取一次元件的原始碼
    test.beforeAll(() => {
        taskListCode = fs.readFileSync(path.resolve('src/frontend/components/TaskList.js'), 'utf-8');
    });

    // 測試案例 1: 成功從 API 載入並渲染初始任務列表
    test('should render initial tasks correctly from API mock', async ({ page }) => {
        const mockTasks = [
            { id: 'task-1', status: 'processing', type: 'transcribe', payload: { original_filename: 'audio.mp3' }, result: { message: '處理中...' } },
            { id: 'task-2', status: 'completed', type: 'youtube', payload: { url: 'video.mp4' }, result: { output_path: '/files/video.mp4' } }
        ];

        await page.route(`${baseURL}/api/tasks`, route => {
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockTasks) });
        });

        // 關鍵修正：加入 <base> 標籤，讓相對路徑的 fetch('/api/tasks') 能被正確解析
        await page.setContent(`<base href="${baseURL}"><div id="task-list-container"></div>`);

        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { TaskList } = await import(dataUrl);
            const container = document.getElementById('task-list-container');
            const taskList = new TaskList(container, {
                showStatusMessage: () => {},
                openPreviewModal: () => {},
            });
            await taskList.init();
        }, taskListCode);

        const ongoingTask = page.locator('#ongoing-tasks .task-item[data-task-id="task-1"]');
        await expect(ongoingTask).toBeVisible();
        await expect(ongoingTask).toContainText('audio.mp3');

        const completedTask = page.locator('#completed-tasks .task-item[data-task-id="task-2"]');
        await expect(completedTask).toBeVisible();
        await expect(completedTask).toContainText('video.mp4');
    });

    // 測試案例 2: 處理新的和更新的任務
    test('should handle real-time updates for new and completed tasks', async ({ page }) => {
        await page.route(`${baseURL}/api/tasks`, route => route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }));

        await page.setContent(`<base href="${baseURL}"><div id="task-list-container"></div>`);

        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { TaskList } = await import(dataUrl);
            const container = document.getElementById('task-list-container');
            const taskList = new TaskList(container, {
                 showStatusMessage: () => {},
                 openPreviewModal: () => {},
            });
            await taskList.init();
            window.taskList = taskList;
        }, taskListCode);

        await expect(page.locator('#no-ongoing-task-msg')).toBeVisible();

        const newTaskPayload = { task_id: 'task-new-1', status: 'processing', filename: 'new_file.wav', task_type: 'transcribe', message: '正在處理' };
        await page.evaluate(payload => window.taskList.handleTaskUpdate(payload), newTaskPayload);
        await expect(page.locator('#ongoing-tasks .task-item[data-task-id="task-new-1"]')).toBeVisible();

        const completedTaskPayload = { task_id: 'task-new-1', status: 'completed', output_path: '/files/new_file.txt' };
        await page.evaluate(payload => window.taskList.handleTaskUpdate(payload), completedTaskPayload);
        await expect(page.locator('#completed-tasks .task-item[data-task-id="task-new-1"]')).toBeVisible();
    });

    // 測試案例 3: API 載入失敗時顯示錯誤訊息
    test('should display an error message when API fetch fails', async ({ page }) => {
        await page.route(`${baseURL}/api/tasks`, route => route.abort('connectionfailed'));

        await page.setContent(`<base href="${baseURL}"><div id="task-list-container"></div>`);

        await page.evaluate(async (code) => {
            const dataUrl = 'data:text/javascript,' + encodeURIComponent(code);
            const { TaskList } = await import(dataUrl);
            const container = document.getElementById('task-list-container');
            const taskList = new TaskList(container, {
                 showStatusMessage: () => {},
                 openPreviewModal: () => {},
            });
            await taskList.init();
        }, taskListCode);

        const container = page.locator('#task-list-container');
        await expect(container).toContainText('載入任務列表失敗');
    });
});
