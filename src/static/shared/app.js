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
        statusHtml = `<div class="task-actions">
                        <a href="/api/download/${task.task_id}" class="button-like btn-download">下載</a>
                      </div>`;
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

    socket.onopen = () => updateStateAndRender({ connectionStatus: 'connected' });
    socket.onclose = () => {
        updateStateAndRender({ connectionStatus: 'disconnected' });
        setTimeout(setupWebSocket, 3000);
    };
    socket.onerror = () => updateStateAndRender({ connectionStatus: 'disconnected' });

    socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        const { payload } = message;
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

export const AppInitializer = {
    init: function(pageConfig = {}) {
        document.addEventListener('DOMContentLoaded', async () => {
            if (pageConfig.pageId) {
                setActiveNavButton(pageConfig.pageId);
            }
            setupWebSocket();
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
