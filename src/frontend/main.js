import { FileBrowser } from './components/FileBrowser.js';
import { TaskList } from './components/TaskList.js';

/**
 * 應用程式主進入點
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM 已載入，開始初始化應用程式。');

    const appContainer = document.getElementById('app');
    if (!appContainer) {
        console.error('找不到應用程式根容器 #app');
        return;
    }

    // --- 全域輔助函式 (從 mp3.html 遷移) ---

    const statusMessageArea = document.getElementById('status-message-area');
    const statusMessageText = document.getElementById('status-message-text');

    /**
     * 顯示一個帶有顏色和自動隱藏功能的狀態訊息。
     */
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
                // 僅當訊息未被更新時才隱藏
                if (statusMessageText.textContent === message) {
                    statusMessageArea.style.display = 'none';
                }
            }, duration);
        }
    };

    /**
     * 開啟預覽彈窗的邏輯 (目前為 placeholder)。
     * 註：完整的 Modal 實作較為複雜，暫時省略以專注於核心遷移。
     */
    const openPreviewModal = (previewUrl, filename, fileType, taskId) => {
        console.log(`請求開啟預覽: ${filename} (URL: ${previewUrl}, Type: ${fileType}, TaskID: ${taskId})`);
        // 由於完整的 Modal HTML/CSS/JS 尚未遷移，此處使用 alert 作為暫時替代方案。
        alert(`預覽功能觸發成功！\n\n檔案: ${filename}\n類型: ${fileType}\n路徑: ${previewUrl}`);
    };


    // --- 初始化組件 ---

    // 檔案總管 (保持不變)
    const fileBrowserContainer = document.createElement('div');
    appContainer.appendChild(fileBrowserContainer);
    const fileBrowser = new FileBrowser(fileBrowserContainer);
    fileBrowser.init();

    // 間距
    const spacer = document.createElement('div');
    spacer.style.height = '24px';
    appContainer.appendChild(spacer);

    // 任務列表 (傳入相依性)
    const taskListContainer = document.createElement('div');
    appContainer.appendChild(taskListContainer);
    const taskList = new TaskList(taskListContainer, {
        showStatusMessage,
        openPreviewModal
    });
    taskList.init();


    // --- WebSocket 邏輯 (從 mp3.html 遷移) ---
    let socket;

    const handleWebSocketMessage = (message) => {
        console.log(`[WebSocket Received]:`, message);
        const { type, payload } = message;

        // 將與任務相關的訊息分派給 TaskList 組件
        const taskRelatedTypes = [
            'TRANSCRIPTION_STATUS',
            'TRANSCRIPTION_UPDATE',
            'YOUTUBE_STATUS',
            'DOWNLOAD_STATUS'
        ];

        if (taskRelatedTypes.includes(type)) {
             if (payload && payload.task_id) {
                taskList.handleTaskUpdate(payload);
             } else if (type === 'DOWNLOAD_STATUS' && payload && payload.model) {
                // 模型下載狀態可以由其他組件處理，暫時僅記錄
                console.log(`模型下載狀態: ${payload.model} - ${payload.status}`);
             }
        }
        // 未來可以在此處處理其他類型的全域訊息
    };

    const setupWebSocket = () => {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`;
        socket = new WebSocket(wsUrl);

        socket.onopen = () => console.log('WebSocket 連線成功 (新架構)');
        socket.onmessage = (event) => handleWebSocketMessage(JSON.parse(event.data));
        socket.onclose = () => {
            console.log('WebSocket 連線已關閉，3 秒後嘗試重連...');
            setTimeout(setupWebSocket, 3000);
        };
        socket.onerror = (error) => console.error('WebSocket 發生錯誤:', error);
    };

    // 啟動 WebSocket
    setupWebSocket();
});
