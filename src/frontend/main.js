import { FileBrowser } from './components/FileBrowser.js';
import { TaskList } from './components/TaskList.js';

/**
 * 應用程式主進入點
 *
 * 當 DOM 載入完成後，初始化所有根組件。
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM 已載入，開始初始化應用程式。');

    const appContainer = document.getElementById('app');

    if (appContainer) {
        // 初始化檔案總管組件
        const fileBrowserContainer = document.createElement('div');
        appContainer.appendChild(fileBrowserContainer);

        const fileBrowser = new FileBrowser(fileBrowserContainer);
        fileBrowser.init();

        // 為組件之間增加一點間距
        const spacer = document.createElement('div');
        spacer.style.height = '24px';
        appContainer.appendChild(spacer);

        // 初始化任務列表組件
        const taskListContainer = document.createElement('div');
        appContainer.appendChild(taskListContainer);

        const taskList = new TaskList(taskListContainer);
        taskList.init();

    } else {
        console.error('找不到應用程式根容器 #app');
    }
});
