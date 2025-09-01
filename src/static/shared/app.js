/**
 * @file src/static/shared/app.js
 * @description 全站共享的核心 JavaScript 邏輯。
 *              負責狀態管理、WebSocket 通訊、以及通用 UI 元素的渲染。
 *              使用模組模式導出一個 AppInitializer 物件。
 */

// --- 唯一的事實來源 (Single Source of Truth) ---
let globalState = {
    connectionStatus: 'connecting',
    systemStats: { cpu: '--%', ram: '--%', gpu: '--%', gpu_detected: false },
    tasks: [],
    // 更多狀態可以按需添加
};

// --- 輔助函式 ---

/**
 * 深度合併兩個物件，並正確處理陣列（陣列會被替換，而不是合併）。
 * @param {object} target - 目標物件。
 * @param {object} source - 來源物件。
 * @returns {object} 合併後的物件。
 */
function deepMerge(target, source) {
    const output = { ...target };
    if (target && typeof target === 'object' && source && typeof source === 'object') {
        Object.keys(source).forEach(key => {
            if (Array.isArray(source[key])) {
                output[key] = source[key];
            } else if (source[key] && typeof source[key] === 'object' && key in target) {
                output[key] = deepMerge(target[key], source[key]);
            } else {
                output[key] = source[key];
            }
        });
    }
    return output;
}

/**
 * 顯示一個帶有顏色和可選自動隱藏功能的狀態訊息。
 * @param {string} message - 要顯示的訊息。
 * @param {boolean} isError - 是否為錯誤訊息 (紅色)。
 * @param {number} [duration=5000] - 訊息顯示的毫秒數。0 表示永久顯示。
 */
function showStatusMessage(message, isError = false, duration = 5000) {
    const statusArea = document.getElementById('status-message-area');
    const statusText = document.getElementById('status-message-text');
    if (!statusArea || !statusText) {
        console.warn('Status message elements not found in the DOM.');
        return;
    }

    statusText.textContent = message;
    statusArea.style.display = 'block';
    if (isError) {
        statusArea.style.backgroundColor = '#f8d7da';
        statusArea.style.borderColor = '#f5c6cb';
        statusText.style.color = '#721c24';
    } else {
        statusArea.style.backgroundColor = '#d4edda';
        statusArea.style.borderColor = '#c3e6cb';
        statusText.style.color = '#155724';
    }

    if (duration > 0) {
        setTimeout(() => {
            // 僅當訊息未被更新時才隱藏
            if (statusText.textContent === message) {
                statusArea.style.display = 'none';
            }
        }, duration);
    }
}


// --- 核心渲染邏輯 ---

/**
 * 根據 globalState 渲染全域儀表板。
 */
function renderDashboard() {
    const { connectionStatus, systemStats } = globalState;

    const statusTextEl = document.getElementById('status-text');
    const statusLightEl = document.getElementById('status-light');
    if (statusTextEl && statusLightEl) {
        statusLightEl.classList.remove('status-green', 'status-yellow');
        if (connectionStatus === 'connected') {
            statusTextEl.textContent = '已連線';
            statusLightEl.classList.add('status-green');
        } else {
            statusTextEl.textContent = '已離線';
            statusLightEl.classList.add('status-yellow');
        }
    }

    const cpuLabelEl = document.getElementById('cpu-label');
    if (cpuLabelEl) cpuLabelEl.textContent = `${systemStats.cpu}%`;

    const ramLabelEl = document.getElementById('ram-label');
    if (ramLabelEl) ramLabelEl.textContent = `${systemStats.ram}%`;

    const gpuDisplayEl = document.getElementById('gpu-display');
    if (gpuDisplayEl) gpuDisplayEl.textContent = systemStats.gpu_detected ? '已偵測到' : '未偵測到';

    const gpuLabelEl = document.getElementById('gpu-label');
    if (gpuLabelEl) gpuLabelEl.textContent = systemStats.gpu_detected ? `${systemStats.gpu}%` : '--%';
}

/**
 * 創建單個任務項目的 HTML 字串。
 * @param {object} task - 任務物件。
 * @returns {string} 任務項目的 HTML。
 */
function getTaskHtml(task) {
    const isOngoing = ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(task.status);
    const displayName = (task.result && task.result.video_title) || task.filename || task.url || task.task_id;
    const fullDisplayName = task.filename || task.url || task.task_id;
    const taskType = task.task_type_display || task.type;

    let statusHtml = '';
    if (isOngoing) {
        const elapsed = task.startTime ? `(經過時間: ${Math.floor((Date.now() - task.startTime) / 1000)}s)` : '';
        statusHtml = `<span class="task-status status-processing">${task.message || task.status}</span> <span class="timer">${elapsed}</span>`;
    } else if (task.status === 'completed') {
        const resultData = task.result || {};
        const outputPath = resultData.output_path || resultData.transcript_path || '';
        if (outputPath) {
            statusHtml = `
                <div class="task-actions">
                    <a href="#" class="btn-preview" data-task-id="${task.task_id}" data-output-path="${outputPath}" data-filename="${displayName}">預覽</a>
                    <a href="/api/download/${task.task_id}" class="btn-download" download>下載</a>
                </div>`;
        } else {
            statusHtml = `<span class="task-status status-completed">完成 (無輸出)</span>`;
        }
    } else { // failed
        statusHtml = `<span class="task-status status-failed">${task.status}: ${task.error || '未知錯誤'}</span>`;
    }

    return `
        <div class="task-item" data-task-id="${task.task_id}">
            <div style="flex-grow: 1; overflow: hidden; margin-right: 10px; min-width: 0;">
                <span class="task-filename" title="${fullDisplayName}">${displayName} (${taskType})</span>
            </div>
            <span class="task-status" style="flex-shrink: 0; text-align: right; min-width: 100px;">
                ${statusHtml}
            </span>
        </div>`;
}

/**
 * 渲染所有任務列表（處理中、已完成等）。
 * 這個函式現在能處理通用的任務列表以及 YouTube 報告專屬的瀏覽區。
 */
function renderTaskLists() {
    const { tasks } = globalState;

    const ongoingTasksContainer = document.getElementById('ongoing-tasks');
    const completedTasksContainer = document.getElementById('completed-tasks');
    const youtubeReportsContainer = document.getElementById('youtube-file-browser');

    const ongoingTasks = tasks.filter(t => ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(t.status));

    // 將 YouTube 報告與其他已完成任務分開
    const youtubeReports = tasks.filter(t => t.type === 'gemini_process' && (t.status === 'completed' || t.status === 'failed'));
    const otherFinishedTasks = tasks.filter(t => t.type !== 'gemini_process' && (t.status === 'completed' || t.status === 'failed'));


    // 渲染處理中任務
    if (ongoingTasksContainer) {
        if (ongoingTasks.length > 0) {
            ongoingTasksContainer.innerHTML = ongoingTasks.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)).map(getTaskHtml).join('');
        } else {
            ongoingTasksContainer.innerHTML = `<p id="no-ongoing-task-msg">暫無執行中任務</p>`;
        }
    }

    // 渲染通用的已完成任務
    if (completedTasksContainer) {
        if (otherFinishedTasks.length > 0) {
            completedTasksContainer.innerHTML = otherFinishedTasks.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)).map(getTaskHtml).join('');
        } else {
            completedTasksContainer.innerHTML = `<p id="no-completed-task-msg">尚無完成的任務</p>`;
        }
    }

    // 專門渲染 YouTube 報告
    if (youtubeReportsContainer) {
        if (youtubeReports.length > 0) {
            youtubeReportsContainer.innerHTML = youtubeReports.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0)).map(getTaskHtml).join('');
        } else {
            youtubeReportsContainer.innerHTML = `<p id="no-youtube-report-msg">尚無已完成的報告</p>`;
        }
    }
}

/**
 * 主渲染函式，根據全域狀態更新所有 UI。
 */
function renderUI() {
    renderDashboard();
    renderTaskLists();
    // 每個頁面可以傳入自己的特定渲染函式
}

// --- 狀態與通訊 ---

/**
 * 更新全域狀態並觸發 UI 重新渲染。
 * @param {object} partialNewState - 部分新狀態。
 */
function updateStateAndRender(partialNewState) {
    globalState = deepMerge(globalState, partialNewState);
    renderUI();
}

/**
 * 設定並管理 WebSocket 連線。
 */
function setupWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('WebSocket 連線成功');
        updateStateAndRender({ connectionStatus: 'connected' });
    };

    socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        console.log('[WebSocket Received]:', message);
        const { type, payload } = message;

        let tasks = [...globalState.tasks];
        const taskIndex = tasks.findIndex(t => t.task_id === payload.task_id);

        if (taskIndex !== -1) {
            tasks[taskIndex] = { ...tasks[taskIndex], ...payload };
        } else {
            tasks.push({ ...payload, timestamp: Date.now() });
        }
        updateStateAndRender({ tasks });
    };

    socket.onclose = () => {
        console.log('WebSocket 連線已關閉，3 秒後重試...');
        updateStateAndRender({ connectionStatus: 'disconnected' });
        setTimeout(setupWebSocket, 3000);
    };

    socket.onerror = (error) => {
        console.error('WebSocket 發生錯誤:', error);
        updateStateAndRender({ connectionStatus: 'disconnected' });
    };
}


// --- 導出的 AppInitializer ---

export const AppInitializer = {
    /**
     * 初始化應用程式的核心功能。
     * @param {object} [pageConfig={}] - 特定於頁面的設定。
     * @param {function} [pageConfig.pageSpecificRender] - 頁面專屬的額外渲染函式。
     */
    init: async function(pageConfig = {}) {
        document.addEventListener('DOMContentLoaded', async () => {
            // 啟動 WebSocket
            setupWebSocket();

            // 獲取初始任務列表
            try {
                const response = await fetch('/api/tasks');
                if (!response.ok) throw new Error('無法獲取任務列表');
                const tasks = await response.json();
                updateStateAndRender({ tasks: tasks || [] });
            } catch (error) {
                console.error('獲取初始任務失敗:', error);
                showStatusMessage('無法載入歷史任務', true);
            }

            // 設定定時更新儀表板
            setInterval(async () => {
                try {
                    const response = await fetch('/api/system_stats');
                    const stats = await response.json();
                    updateStateAndRender({ systemStats: stats });
                } catch (error) {
                    // 靜默失敗，避免過多 log
                }
            }, 2000);

            // 如果有頁面專屬的渲染邏輯，將其加入主渲染循環
            if (pageConfig.pageSpecificRender) {
                const originalRenderUI = renderUI;
                renderUI = () => {
                    originalRenderUI();
                    pageConfig.pageSpecificRender();
                }
            }
        });
    }
};

// 將常用函式附加到導出物件上，方便單獨使用
AppInitializer.showStatusMessage = showStatusMessage;

// --- For Testing Purposes ---
// Expose a handler to the window object only in a test environment.
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.__handleTestWebSocketMessage = (message) => {
        const { type, payload } = message;
        let tasks = [...globalState.tasks];
        const taskIndex = tasks.findIndex(t => t.task_id === payload.task_id);

        if (taskIndex !== -1) {
            // 更新現有任務
            tasks[taskIndex] = { ...tasks[taskIndex], ...payload, timestamp: Date.now() };
        } else {
            // 新增任務
            tasks.push({ ...payload, timestamp: Date.now() });
        }
        updateStateAndRender({ tasks });
    };

    // 為了測試方便，也暴露一個更新狀態的通用函式
    window.__updateTestState = (partialState) => {
        updateStateAndRender(partialState);
    };
}
