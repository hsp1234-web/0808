/**
 * @file src/static/shared/app.js
 * @description 全站共享的核心 JavaScript 邏輯。
 */

let globalState = {
    connectionStatus: 'connecting',
    systemStats: { cpu_usage: '--', ram_usage: '--', gpu_usage: '--', gpu_detected: false },
    tasks: [],
};

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

function showStatusMessage(message, isError = false, duration = 5000) {
    const statusArea = document.getElementById('status-message-area');
    const statusText = document.getElementById('status-message-text');
    if (!statusArea || !statusText) return;
    statusText.textContent = message;
    statusArea.style.display = 'block';
    statusArea.className = `card status-message ${isError ? 'error' : 'success'}`;
    if (duration > 0) {
        setTimeout(() => {
            if (statusText.textContent === message) {
                statusArea.style.display = 'none';
            }
        }, duration);
    }
}

function renderDashboard() {
    const { connectionStatus, systemStats } = globalState;
    const statusTextEl = document.getElementById('status-text');
    const statusLightEl = document.getElementById('status-light');
    if (statusTextEl && statusLightEl) {
        statusLightEl.classList.remove('status-green', 'status-yellow', 'status-red');
        if (connectionStatus === 'connected') {
            statusTextEl.textContent = '已連線';
            statusLightEl.classList.add('status-green');
        } else {
            statusTextEl.textContent = '連線中...';
            statusLightEl.classList.add('status-yellow');
        }
    }
    const cpuLabelEl = document.getElementById('cpu-label');
    if (cpuLabelEl) cpuLabelEl.textContent = `${systemStats.cpu_usage.toFixed(1) || '--'}%`;
    const ramLabelEl = document.getElementById('ram-label');
    if (ramLabelEl) ramLabelEl.textContent = `${systemStats.ram_usage.toFixed(1) || '--'}%`;
    const gpuContainer = document.getElementById('gpu-stat-container');
    if (gpuContainer) {
        if (systemStats.gpu_detected) {
            gpuContainer.style.display = 'flex';
            const gpuLabelEl = document.getElementById('gpu-label');
            if (gpuLabelEl) gpuLabelEl.textContent = `${systemStats.gpu_usage.toFixed(1) || '--'}%`;
        } else {
            gpuContainer.style.display = 'none';
        }
    }
}

function getTaskHtml(task) {
    const isOngoing = ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(task.status);
    const displayName = (task.result && task.result.video_title) || (task.payload && task.payload.original_filename) || task.url || task.task_id;
    const fullDisplayName = (task.payload && task.payload.original_filename) || task.url || task.task_id;
    const taskType = task.type || '未知';

    let statusHtml = '';
    if (isOngoing) {
        const elapsed = task.startTime ? `(${Math.floor((Date.now() - task.startTime) / 1000)}s)` : '';
        statusHtml = `<span class="task-status status-processing">${task.message || task.status} ${elapsed}</span>`;
    } else if (task.status === 'completed') {
        const buttons = [];

        // JULES'S FIX (2025-09-01): 擴大條件判斷，以涵蓋所有應被視為「報告」的任務類型。
        // 舊的邏輯只檢查 'gemini_process'，但後端可能會回傳 'youtube_process_chain'
        // 或甚至是 'youtube_download_only' 作為最終的完成類型。
        const isReportTask = ['gemini_process', 'youtube_process_chain', 'youtube_download_only'].includes(task.type);

        if (isReportTask) {
            const result = task.result || {};
            const outputPath = result.output_path || '';

            // 如果沒有輸出路徑，則不顯示任何按鈕
            if (outputPath) {
                const extension = outputPath.includes('.html') ? '.html' : '.txt';
                const fileType = extension === '.html' ? 'text/html' : 'text/plain';

                // 1. 詳細資料按鈕
                buttons.push(`<button class="button-like btn-details" data-task-id="${task.task_id}" data-testid="task-details-button">詳細資料</button>`);
                // 2. 預覽按鈕
                buttons.push(`<button class="button-like btn-preview" data-task-id="${task.task_id}" data-file-type="${fileType}" data-testid="task-preview-button">預覽</button>`);
                // 3. 下載產出按鈕
                buttons.push(`<a href="/api/download/${task.task_id}?type=artifact" class="button-like btn-download" data-testid="task-download-button">下載產出</a>`);
            }

        } else { // 處理 'transcribe' 和 'download' 任務
            // JULES'S FIX (2025-09-01): 根據 Code Review 的回饋，完整還原轉錄和下載任務的按鈕。
            // 確保「預覽媒體」按鈕能正確顯示。

            // 1. 下載產出按鈕 (例如：逐字稿 .txt)
            buttons.push(`<a href="/api/download/${task.task_id}?type=artifact" class="button-like btn-download" data-testid="task-download-button">下載產出</a>`);

            // 2. 預覽媒體按鈕 (例如：原始的 .mp3 音訊檔)
            // 這裡的 output_path 通常指向原始的上傳或下載檔案，而不是轉錄結果。
            const result = task.result || {};
            if ((task.type === 'transcribe' || task.type === 'download') && result.output_path) {
                 buttons.push(`<a href="${result.output_path}" target="_blank" class="button-like btn-preview" data-testid="task-preview-media-button">預覽媒體</a>`);
            }
        }

        statusHtml = `<div class="task-actions">${buttons.join('')}</div>`;
    } else {
        statusHtml = `<span class="task-status status-failed">${task.status}: ${task.error || '未知錯誤'}</span>`;
    }

    return `<div class="task-item" data-task-id="${task.task_id}">
                <span class="task-filename" title="${fullDisplayName}">${displayName} (${taskType})</span>
                ${statusHtml}
            </div>`;
}

function renderTaskLists() {
    const { tasks } = globalState;
    const ongoingTasksContainer = document.getElementById('ongoing-tasks');
    const completedTasksContainer = document.getElementById('completed-tasks');
    const youtubeReportsContainer = document.getElementById('youtube-file-browser');

    const ongoingTasks = tasks.filter(t => ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(t.status));
    const finishedTasks = tasks.filter(t => ['completed', 'failed'].includes(t.status));

    const youtubeReports = finishedTasks.filter(t => t.type === 'gemini_process');
    const otherCompletedTasks = finishedTasks.filter(t => t.type !== 'gemini_process');

    if (ongoingTasksContainer) {
        ongoingTasksContainer.innerHTML = ongoingTasks.length > 0 ? ongoingTasks.map(getTaskHtml).join('') : `<p>暫無執行中任務</p>`;
    }
    if (completedTasksContainer) {
        completedTasksContainer.innerHTML = otherCompletedTasks.length > 0 ? otherCompletedTasks.map(getTaskHtml).join('') : `<p>尚無完成的任務</p>`;
    }
    if (youtubeReportsContainer) {
        youtubeReportsContainer.innerHTML = youtubeReports.length > 0 ? youtubeReports.map(getTaskHtml).join('') : `<p>尚無已完成的報告</p>`;
    }
}

function updateStateAndRender(partialNewState) {
    globalState = deepMerge(globalState, partialNewState);
    renderUI();
}

function setupWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`;
    const socket = new WebSocket(wsUrl);

    // 在 AppInitializer 上儲存 socket 實例，以便頁面專屬腳本可以存取
    AppInitializer.socket = socket;

    socket.onopen = () => updateStateAndRender({ connectionStatus: 'connected' });
    socket.onclose = () => {
        updateStateAndRender({ connectionStatus: 'disconnected' });
        setTimeout(setupWebSocket, 3000);
    };
    socket.onerror = () => updateStateAndRender({ connectionStatus: 'disconnected' });

    socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        const { type, payload } = message;

        if (type === 'DOWNLOAD_STATUS') {
            const modelProgressContainer = document.getElementById('model-progress-container');
            const modelProgressBar = document.getElementById('model-progress-bar');
            const modelProgressText = document.getElementById('model-progress-text');
            const confirmBtn = document.getElementById('confirm-settings-btn');

            if (modelProgressContainer && modelProgressBar && modelProgressText) {
                modelProgressContainer.classList.remove('hidden');
                modelProgressBar.style.width = `${payload.percent || 0}%`;
                modelProgressText.textContent = payload.description || payload.status;

                if (payload.status === 'completed' || payload.status === 'failed') {
                    if(confirmBtn) confirmBtn.disabled = false;
                    if (payload.status === 'completed') {
                        modelProgressBar.style.backgroundColor = 'var(--status-green)';
                        setTimeout(() => modelProgressContainer.classList.add('hidden'), 2000);
                    } else {
                         modelProgressBar.style.backgroundColor = 'var(--status-red)';
                    }
                }
            }
            return; // Stop processing here for this message type
        }

        let tasks = [...globalState.tasks];
        const taskIndex = tasks.findIndex(t => t.task_id === payload.task_id);

        const updatedTask = { ...(taskIndex !== -1 ? tasks[taskIndex] : {}), ...payload, timestamp: Date.now() };
        if (updatedTask.status === 'starting' || (updatedTask.status === 'downloading' && !updatedTask.startTime)) {
            updatedTask.startTime = Date.now();
        }

        if (taskIndex !== -1) {
            tasks[taskIndex] = updatedTask;
        } else {
            tasks.push(updatedTask);
        }
        updateStateAndRender({ tasks });
    };
}

function setActiveNavButton(pageId) {
    document.querySelectorAll('.nav-button').forEach(button => {
        button.classList.toggle('active', button.dataset.page === pageId);
    });
}

function renderUI() {
    renderDashboard();
    renderTaskLists();
}

// --- Modal Logic ---

function openPreviewModal(task) {
    const modal = document.getElementById('preview-modal');
    const title = document.getElementById('modal-title');
    const body = modal.querySelector('.modal-body');
    const result = task.result || {};
    const outputPath = result.output_path || '';
    const fileType = outputPath.includes('.html') ? 'text/html' : 'text/plain';

    title.textContent = `預覽: ${ (result.video_title || task.payload.original_filename) }`;
    body.innerHTML = '正在載入預覽...';

    if (fileType === 'text/html') {
        const iframe = document.createElement('iframe');
        iframe.src = outputPath;
        iframe.style.width = '100%';
        iframe.style.height = '75vh';
        iframe.style.border = 'none';
        body.innerHTML = '';
        body.appendChild(iframe);
    } else { // text/plain
        fetch(outputPath)
            .then(res => res.text())
            .then(text => {
                const pre = document.createElement('pre');
                pre.style.whiteSpace = 'pre-wrap';
                pre.textContent = text;
                body.innerHTML = '';
                body.appendChild(pre);
            })
            .catch(err => {
                body.textContent = `預覽載入失敗: ${err.message}`;
            });
    }
    modal.style.display = 'flex';
}

function openDetailsModal(task) {
    const modal = document.getElementById('details-modal');
    const title = document.getElementById('details-modal-title');
    const body = document.getElementById('details-modal-body');
    const result = task.result || {};

    title.textContent = `任務詳細資訊: ${ (result.video_title || task.payload.original_filename) }`;
    body.innerHTML = `
        <p><strong>總執行時間:</strong> ${result.processing_duration_seconds || 'N/A'} 秒</p>
        <p><strong>總 Token 消耗:</strong> ${result.total_tokens_used || 'N/A'} tokens</p>
        <p><strong>報告類型:</strong> ${ (result.output_path || '').includes('.html') ? 'HTML' : 'TXT'}</p>
        <p><strong>任務 ID:</strong> <small>${task.task_id}</small></p>
    `;
    modal.style.display = 'flex';
}

function setupModalListeners() {
    const previewModal = document.getElementById('preview-modal');
    const detailsModal = document.getElementById('details-modal');

    const closeModal = (modal) => {
        if (modal) modal.style.display = 'none';
    };

    // Close buttons
    document.getElementById('modal-close-btn')?.addEventListener('click', () => closeModal(previewModal));
    document.getElementById('details-modal-close-btn')?.addEventListener('click', () => closeModal(detailsModal));
    document.getElementById('details-modal-ok-btn')?.addEventListener('click', () => closeModal(detailsModal));

    // Clicking on the overlay
    previewModal?.addEventListener('click', (e) => e.target === previewModal && closeModal(previewModal));
    detailsModal?.addEventListener('click', (e) => e.target === detailsModal && closeModal(detailsModal));

    // Event delegation for dynamically created buttons
    document.body.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('btn-preview') || target.classList.contains('btn-details')) {
            const taskId = target.dataset.taskId;
            const task = globalState.tasks.find(t => t.task_id === taskId);
            if (task) {
                if (target.classList.contains('btn-preview')) {
                    openPreviewModal(task);
                } else if (target.classList.contains('btn-details')) {
                    openDetailsModal(task);
                }
            }
        }
    });
}


export const AppInitializer = {
    socket: null,
    getSocket: function() {
        return this.socket;
    },
    init: function(pageConfig = {}) {
        document.addEventListener('DOMContentLoaded', async () => {
            if (pageConfig.pageId) {
                setActiveNavButton(pageConfig.pageId);
            }
            setupWebSocket();
            setupModalListeners(); // Set up modal listeners
            try {
                const response = await fetch('/api/tasks');
                const tasks = await response.json();
                updateStateAndRender({ tasks: tasks || [] });
            } catch (error) {
                showStatusMessage('無法載入歷史任務', true);
            }
            const fetchSystemStats = async () => {
                try {
                    const response = await fetch('/api/system_stats');
                    if (response.ok) {
                        const stats = await response.json();
                        updateStateAndRender({ systemStats: stats });
                    }
                } catch (error) { /* silent fail */ }
            };
            fetchSystemStats();
            setInterval(fetchSystemStats, 2000);
        });
    }
};

AppInitializer.showStatusMessage = showStatusMessage;

// --- For Testing Purposes ---
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.__handleTestWebSocketMessage = (message) => {
        const { type, payload } = message;
        let tasks = [...globalState.tasks];
        const taskIndex = tasks.findIndex(t => t.task_id === payload.task_id);
        if (taskIndex !== -1) {
            tasks[taskIndex] = { ...tasks[taskIndex], ...payload, timestamp: Date.now() };
        } else {
            tasks.push({ ...payload, timestamp: Date.now() });
        }
        updateStateAndRender({ tasks });
    };
    window.__updateTestState = (partialState) => {
        updateStateAndRender(partialState);
    };
}
