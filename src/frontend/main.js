import { YouTubeReporter } from './components/YouTubeReporter.js';
import { apiService } from './ApiService.js';

/**
 * 應用程式主進入點
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM 已載入，開始初始化應用程式 (v2 - 組件化)。');

    const appContainer = document.getElementById('app');
    if (!appContainer) {
        console.error('找不到應用程式根容器 #app');
        return;
    }

    // 清空容器，為組件化渲染做準備
    appContainer.innerHTML = '';

    // --- 全域輔助函式 ---
    const statusMessageArea = document.getElementById('status-message-area');
    const statusMessageText = document.getElementById('status-message-text');

    const showStatusMessage = (message, isError = false, duration = 5000) => {
        if (!statusMessageArea || !statusMessageText) {
            console.log(`Status (${isError ? 'ERROR' : 'INFO'}): ${message}`);
            return;
        }
        statusMessageText.textContent = message;
        statusMessageArea.style.display = 'block';
        statusMessageArea.style.backgroundColor = isError ? '#f8d7da' : '#d4edda';
        statusMessageArea.style.borderColor = isError ? '#f5c6cb' : '#c3e6cb';
        statusMessageText.style.color = isError ? '#721c24' : '#155724';

        if (duration > 0) {
            setTimeout(() => {
                if (statusMessageText.textContent === message) {
                    statusMessageArea.style.display = 'none';
                }
            }, duration);
        }
    };

    const openPreviewModal = (previewUrl, filename, fileType, taskId) => {
        console.log(`請求開啟預覽: ${filename}`);
        alert(`預覽功能觸發成功！\n\n檔案: ${filename}\n類型: ${fileType}\n路徑: ${previewUrl}`);
    };

    const logAction = (action, value = null) => {
        const message = value !== null ? `${action}: ${value}` : action;
        console.log(`Logging action: ${message}`);
        fetch('/api/log/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: message })
        }).catch(err => console.error('logAction failed:', err));
    };

    // 簡易的任務管理器 (未來可擴充)
    const taskManager = {
        startTask(task) {
            console.log('Task Manager: 收到啟動任務請求', task);
            // 在此處可以將任務新增到一個全域狀態，並觸發 WebSocket 訊息
            // 為了專注於遷移 YouTube 組件，暫時只做日誌輸出
        }
    };


    // --- 初始化 YouTube Reporter 組件 ---
    const youtubeReporterContainer = document.createElement('div');
    appContainer.appendChild(youtubeReporterContainer);

    const youtubeReporter = new YouTubeReporter(youtubeReporterContainer, {
        api: apiService,
        showStatusMessage,
        openPreviewModal,
        logAction,
        taskManager
    });
    youtubeReporter.init();

    // WebSocket 邏輯暫時保留，但目前沒有組件會監聽它
    // setupWebSocket();
});
