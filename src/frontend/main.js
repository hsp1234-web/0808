import { FileBrowser } from './components/FileBrowser.js';
import { TaskList } from './components/TaskList.js';
import { LocalTranscriber } from './components/LocalTranscriber.js';
import { MediaDownloader } from './components/MediaDownloader.js';

/**
 * 主應用程式類別
 *
 * 負責協調所有組件、WebSocket 連線和全域狀態。
 */
class App {
    constructor() {
        // DOM 元素
        this.localTranscriberContainer = document.getElementById('local-file-tab');
        this.mediaDownloaderContainer = document.getElementById('downloader-tab');
        this.tasklistContainer = document.getElementById('task-list-container');
        this.fileBrowserContainer = document.getElementById('file-browser-container');
        this.statusMessageArea = document.getElementById('status-message-area');
        this.statusMessageText = document.getElementById('status-message-text');
        this.modelDisplay = document.getElementById('model-display');

        // 服務與狀態
        this.socket = null;
    }

    /**
     * 初始化 WebSocket 連線。
     */
    setupWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`;
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('WebSocket 連線成功');
            this.logAction('websocket-connect-success');
        };

        this.socket.onmessage = (event) => this.handleWebSocketMessage(JSON.parse(event.data));

        this.socket.onclose = () => {
            console.log('WebSocket 連線已關閉，正在嘗試重新連線...');
            this.logAction('websocket-connect-close');
            setTimeout(() => this.setupWebSocket(), 3000);
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket 發生錯誤:', error);
            this.logAction('websocket-connect-error');
        };
    }

    /**
     * 根據訊息類型，將 WebSocket 訊息分派給對應的組件。
     * @param {object} message - 從 WebSocket 收到的已解析的 JSON 訊息。
     */
    handleWebSocketMessage(message) {
        console.log('[WebSocket Received]:', message);
        const { type, payload } = message;

        if (type === 'DOWNLOAD_STATUS') {
            // 這個訊息由 LocalTranscriber 處理
            if (this.localTranscriber) {
                this.localTranscriber.handleModelDownloadStatus(payload);
            }
        } else if (['TRANSCRIPTION_STATUS', 'TRANSCRIPTION_UPDATE', 'YOUTUBE_STATUS'].includes(type)) {
            // 這些是任務狀態更新，由 TaskList 處理
            if (this.taskList) {
                this.taskList.handleTaskUpdate(payload);
            }
        } else {
            console.warn(`未知的 WebSocket 訊息類型: ${type}`);
        }
    }

    /**
     * 顯示一個帶有顏色和自動隱藏功能的狀態訊息。
     * @param {string} message - 要顯示的訊息。
     * @param {boolean} isError - 是否為錯誤訊息 (紅色)。
     * @param {number} duration - 訊息顯示的毫秒數。
     */
    showStatusMessage(message, isError = false, duration = 5000) {
        if (!this.statusMessageArea || !this.statusMessageText) return;
        this.statusMessageText.textContent = message;
        this.statusMessageArea.style.display = 'block';
        this.statusMessageArea.style.backgroundColor = isError ? '#f8d7da' : '#d4edda';
        this.statusMessageArea.style.borderColor = isError ? '#f5c6cb' : '#c3e6cb';
        this.statusMessageText.style.color = isError ? '#721c24' : '#155724';

        if (duration > 0) {
            setTimeout(() => {
                if (this.statusMessageText.textContent === message) {
                    this.statusMessageArea.style.display = 'none';
                }
            }, duration);
        }
    }

    /**
     * 記錄使用者操作到後端。
     * @param {string} action - 操作名稱。
     * @param {any} value - 操作的相關值。
     */
    logAction(action, value = null) {
        const message = value !== null ? `${action}: ${value}` : action;
        console.log(`Logging action: ${message}`);
        fetch('/api/log/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: message })
        }).catch(err => console.error('logAction failed:', err));
    }

    /**
     * 設定頁籤切換邏輯。
     */
    setupTabSwitching() {
        const tabContainer = document.querySelector('.tab-container');
        const tabContentContainer = document.getElementById('tab-content-container');

        if (!tabContainer || !tabContentContainer) return;

        tabContainer.addEventListener('click', (e) => {
            if (e.target.matches('.tab-button')) {
                const tabId = e.target.dataset.tab;
                this.logAction('click-tab', tabId);

                // 更新按鈕的 active 狀態
                tabContainer.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                e.target.classList.add('active');

                // 更新內容的 active 狀態
                tabContentContainer.querySelectorAll('.tab-content').forEach(content => {
                    if (content.id === tabId) {
                        content.classList.add('active');
                    } else {
                        content.classList.remove('active');
                    }
                });
            }
        });
    }

    /**
     * 初始化所有組件。
     */
    initComponents() {
        const services = {
            socket: this.socket,
            showStatusMessage: this.showStatusMessage.bind(this),
            logAction: this.logAction.bind(this),
            updateModelDisplay: (modelName) => {
                if (this.modelDisplay) this.modelDisplay.textContent = modelName;
            },
            // 傳入 App 實例，以便組件間可以互相呼叫
            app: this,
        };

        // 初始化 LocalTranscriber
        if (this.localTranscriberContainer) {
            this.localTranscriber = new LocalTranscriber(this.localTranscriberContainer, services);
            this.localTranscriber.init();
        }

        // 初始化 MediaDownloader
        if (this.mediaDownloaderContainer) {
            this.mediaDownloader = new MediaDownloader(this.mediaDownloaderContainer, services);
            this.mediaDownloader.init();
        }

        // 初始化 TaskList
        if (this.tasklistContainer) {
            // TaskList 需要一個開啟預覽彈窗的函式
            const taskListServices = {
                ...services,
                openPreviewModal: (url, name, type, id) => alert(`預覽功能待實現: ${name}`),
            };
            this.taskList = new TaskList(this.tasklistContainer, taskListServices);
            this.taskList.init();
        }

        // 初始化 FileBrowser
        if (this.fileBrowserContainer) {
            this.fileBrowser = new FileBrowser(this.fileBrowserContainer, services);
            this.fileBrowser.init();
        }
    }

    /**
     * 啟動應用程式。
     */
    init() {
        console.log('DOM 已載入，開始初始化應用程式。');
        this.setupWebSocket();
        this.initComponents();
        this.setupTabSwitching();
    }
}

// 當 DOM 載入完成後，啟動 App
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
});
