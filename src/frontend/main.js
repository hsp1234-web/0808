import { FileBrowser } from './components/FileBrowser.js';

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

        // 未來可以在此處初始化其他根層級的組件
        // const taskList = new TaskList(document.getElementById('task-list-container'));
        // taskList.init();

    } else {
        console.error('找不到應用程式根容器 #app');
    }
});
