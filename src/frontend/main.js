import { FileBrowser } from './components/FileBrowser.js';
import { TaskList } from './components/TaskList.js';
import { LocalTranscriber } from './components/LocalTranscriber.js';
import { MediaDownloader } from './components/MediaDownloader.js';
import { YouTubeReporter } from './components/YouTubeReporter.js';
import { LogViewer } from './components/LogViewer.js';

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
        this.youtubeReporterContainer = document.getElementById('youtube-report-tab');
        this.tasklistContainer = document.getElementById('task-list-container');
        this.fileBrowserContainer = document.getElementById('file-browser-container');
        this.logViewerContainer = document.getElementById('log-viewer-container');
        this.statusMessageArea = document.getElementById('status-message-area');
        this.statusMessageText = document.getElementById('status-message-text');

        // JULES: Get new dashboard elements
        this.modelDisplay = document.getElementById('model-display');
        this.statusLight = document.getElementById('status-light');
        this.statusText = document.getElementById('status-text');
        this.gpuDisplay = document.getElementById('gpu-display');
        this.cpuLabel = document.getElementById('cpu-label');
        this.ramLabel = document.getElementById('ram-label');
        this.gpuLabel = document.getElementById('gpu-label');


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
            if (this.statusText) this.statusText.textContent = '已連線';
            if (this.statusLight) this.statusLight.className = 'status-light status-green';
        };

        this.socket.onmessage = (event) => this.handleWebSocketMessage(JSON.parse(event.data));

        this.socket.onclose = () => {
            console.log('WebSocket 連線已關閉，正在嘗試重新連線...');
            this.logAction('websocket-connect-close');
            if (this.statusText) this.statusText.textContent = '已離線';
            if (this.statusLight) this.statusLight.className = 'status-light status-yellow';
            setTimeout(() => this.setupWebSocket(), 3000);
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket 發生錯誤:', error);
            this.logAction('websocket-connect-error');
            if (this.statusText) this.statusText.textContent = '連線錯誤';
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
     * 設定 Modal 彈窗的事件監聽器。
     */
    setupModals() {
        const previewModal = document.getElementById('preview-modal');
        const modalCloseBtn = document.getElementById('modal-close-btn');

        const closePreviewModal = () => {
            this.logAction('close-preview-modal');
            previewModal.style.display = 'none';
            const modalBody = previewModal.querySelector('.modal-body');
            modalBody.innerHTML = ''; // Stop video/audio playback
        };

        if (modalCloseBtn) modalCloseBtn.addEventListener('click', closePreviewModal);
        if (previewModal) {
            previewModal.addEventListener('click', (e) => {
                if (e.target === previewModal) {
                    closePreviewModal();
                }
            });
        }
    }

    /**
     * 開啟預覽 Modal 彈窗並載入內容。
     */
    async openPreviewModal(previewUrl, filename, fileType, taskId) {
        this.logAction('open-preview-modal', taskId);

        const previewModal = document.getElementById('preview-modal');
        const modalTitle = document.getElementById('modal-title');
        const modalBody = previewModal.querySelector('.modal-body');
        const modalDownloadBtn = document.getElementById('modal-download-btn');
        const modalCopyLinkBtn = document.getElementById('modal-copy-link-btn');

        modalBody.innerHTML = '';
        modalTitle.textContent = `預覽: ${filename}`;

        if (fileType.startsWith('video/')) {
            const video = document.createElement('video');
            video.src = previewUrl;
            video.controls = true;
            video.autoplay = true;
            video.style.width = '100%';
            video.style.maxHeight = '75vh';
            modalBody.appendChild(video);
        } else if (fileType.startsWith('audio/')) {
            const audio = document.createElement('audio');
            audio.src = previewUrl;
            audio.controls = true;
            audio.autoplay = true;
            audio.style.width = '100%';
            modalBody.appendChild(audio);
        } else if (fileType === 'text/html') {
            const iframe = document.createElement('iframe');
            iframe.src = previewUrl;
            iframe.style.width = '100%';
            iframe.style.height = '75vh';
            iframe.style.border = 'none';
            modalBody.appendChild(iframe);
        } else if (fileType === 'text/plain') {
            const pre = document.createElement('pre');
            pre.style.whiteSpace = 'pre-wrap';
            pre.textContent = '正在載入預覽...';
            modalBody.appendChild(pre);
            try {
                const response = await fetch(previewUrl);
                if (!response.ok) throw new Error(`伺服器錯誤: ${response.statusText}`);
                pre.textContent = await response.text();
            } catch (error) {
                pre.textContent = `預覽載入失敗: ${error.message}`;
            }
        } else {
            modalBody.innerHTML = `<p>此檔案類型 (${fileType}) 無法直接預覽。</p>`;
        }

        modalDownloadBtn.href = `/api/download/${taskId}`;
        modalDownloadBtn.download = filename;

        modalCopyLinkBtn.onclick = () => {
            const publicUrl = new URL(previewUrl, window.location.origin).href;
            navigator.clipboard.writeText(publicUrl).then(() => {
                this.showStatusMessage('報告連結已複製！', false, 3000);
            });
        };

        previewModal.style.display = 'flex';
    }

    /**
     * 初始化所有組件。
     */
    initComponents() {
        // JULES: 建立一個基礎的 services 物件
        const baseServices = {
            socket: this.socket,
            showStatusMessage: this.showStatusMessage.bind(this),
            logAction: this.logAction.bind(this),
            openPreviewModal: this.openPreviewModal.bind(this), // JULES: Add real function
            app: this, // 傳入 App 實例
        };

        // JULES: 優先初始化 TaskList，因為其他元件會依賴它
        if (this.tasklistContainer) {
            this.taskList = new TaskList(this.tasklistContainer, baseServices);
            this.taskList.init();
        }

        // JULES: 建立給其他主要元件使用的 services 物件，並注入 taskManager
        const services = {
            ...baseServices,
            taskManager: this.taskList, // 將 taskList 實例注入
            updateModelDisplay: (modelName) => {
                if (this.modelDisplay) this.modelDisplay.textContent = modelName;
            },
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

        // 初始化 YouTubeReporter (現在可以存取 taskManager)
        if (this.youtubeReporterContainer) {
            this.youtubeReporter = new YouTubeReporter(this.youtubeReporterContainer, services);
            this.youtubeReporter.init();
        }

        // 初始化 FileBrowser
        if (this.fileBrowserContainer) {
            this.fileBrowser = new FileBrowser(this.fileBrowserContainer, services);
            this.fileBrowser.init();
        }

        // 初始化 LogViewer
        if (this.logViewerContainer) {
            this.logViewer = new LogViewer(this.logViewerContainer, services);
            this.logViewer.init();
        }
    }

    /**
     * 從 API 獲取系統統計數據並更新儀表板。
     */
    async updateSystemStats() {
        try {
            const response = await fetch('/api/system_stats');
            if (!response.ok) return;
            const stats = await response.json();

            if (this.cpuLabel) this.cpuLabel.textContent = `${stats.cpu_usage.toFixed(1)}%`;
            if (this.ramLabel) this.ramLabel.textContent = `${stats.ram_usage.toFixed(1)}%`;
            if (this.gpuDisplay) this.gpuDisplay.textContent = stats.gpu_detected ? '已偵測到' : '未偵測到';
            if (this.gpuLabel) this.gpuLabel.textContent = stats.gpu_detected ? `${stats.gpu_usage.toFixed(1)}%` : '--%';

        } catch (error) {
            console.error("無法更新系統統計數據:", error);
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
        this.setupModals(); // JULES: Add this call

        // JULES: Periodically update system stats
        this.updateSystemStats();
        setInterval(() => this.updateSystemStats(), 2000);
    }
}

// 當 DOM 載入完成後，啟動 App
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
    // JULES'S DEBUGGING: Expose app to the window for E2E testing.
    window.app = app;
});
