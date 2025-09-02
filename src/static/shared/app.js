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

/**
 * 根據任務資訊產生對應的 HTML 字串。
 * @param {object} task - 任務物件。
 * @returns {string} 代表該任務的 HTML 字串。
 */
function getTaskHtml(task) {
    const isOngoing = ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(task.status);
    const result = task.result || {};
    const payload = task.payload || {};

    const displayName = result.video_title || payload.original_filename || task.url || task.task_id;
    const fullDisplayName = payload.original_filename || task.url || task.task_id;
    const taskType = task.type || '未知';

    let statusHtml = '';

    if (isOngoing) {
        const elapsed = task.startTime ? `(${Math.floor((Date.now() - task.startTime) / 1000)}s)` : '';
        statusHtml = `<span class="task-status status-processing">${task.message || task.status} ${elapsed}</span>`;
    } else if (task.status === 'completed') {
        const buttons = [];
        const isReportTask = ['gemini_process', 'youtube_process_chain'].includes(task.type);
        const isTranscriptionTask = task.type === 'transcribe';
        const isDownloadTask = ['download', 'youtube_download_only'].includes(task.type);

        const artifactPath = result.output_path || ''; // 主要產出物 (報告、逐字稿)
        const sourcePath = result.source_path || (isDownloadTask ? artifactPath : ''); // 原始檔 (音訊、影片)

        // 1. 報告任務的專屬按鈕
        if (isReportTask && artifactPath) {
            const fileType = artifactPath.includes('.html') ? 'text/html' : 'text/plain';
            buttons.push(`<button class="button-like btn-details" data-task-id="${task.task_id}" data-testid="task-details-button">詳細資料</button>`);
            buttons.push(`<button class="button-like btn-preview" data-task-id="${task.task_id}" data-file-type="${fileType}" data-testid="task-preview-button">預覽報告</button>`);
            buttons.push(`<a href="/api/download/${task.task_id}?type=artifact" class="button-like btn-download" data-testid="task-download-artifact-button">下載產出</a>`);
        }

        // 2. 轉錄任務的按鈕
        if (isTranscriptionTask) {
            if (result.transcript_path) { // 優先使用專用的逐字稿路徑
                 buttons.push(`<a href="/api/download/${task.task_id}?type=artifact" class="button-like btn-download" data-testid="task-download-artifact-button">下載產出</a>`);
            }
            // 預覽媒體按鈕，指向原始上傳的檔案
            if (result.output_path) {
                buttons.push(`<button class="button-like btn-preview-media" data-task-id="${task.task_id}" data-testid="task-preview-media-button">預覽媒體</button>`);
            }
        }

        // 3. 下載任務的按鈕
        if (isDownloadTask && sourcePath) {
            buttons.push(`<button class="button-like btn-preview-media" data-task-id="${task.task_id}" data-testid="task-preview-media-button">預覽媒體</button>`);
            buttons.push(`<a href="/api/download/${task.task_id}?type=source" class="button-like btn-download" data-testid="task-download-source-button">下載媒體</a>`);
            buttons.push(`<button class="button-like btn-rename" data-task-id="${task.task_id}" data-testid="task-rename-button">修改名稱</button>`);

            const isAudio = /\.(mp3|m4a|wav|flac|ogg)$/i.test(sourcePath);
            if (isAudio) {
                buttons.push(`<button class="button-like btn-send-to-whisper" data-task-id="${task.task_id}" data-testid="task-send-to-transcriber-button">送至轉錄區</button>`);
            }
        }

        statusHtml = `<div class="task-actions">${buttons.join('')}</div>`;
    } else { // FAILED
        statusHtml = `<span class="task-status status-failed" title="${task.error || '未知錯誤'}">${task.status}</span>`;
    }

    return `<div class="task-item" data-task-id="${task.task_id}">
                <span class="task-filename" title="${fullDisplayName}">${displayName} (${taskType})</span>
                ${statusHtml}
            </div>`;
}


/**
 * 根據全域狀態重新渲染所有任務列表。
 */
function renderTaskLists() {
    const { tasks } = globalState;
    const ongoingTasksContainer = document.getElementById('ongoing-tasks');
    const completedTasksContainer = document.getElementById('completed-tasks');
    const youtubeReportsContainer = document.getElementById('youtube-file-browser');

    const ongoingTasks = tasks.filter(t => ['starting', 'downloading', 'processing', 'analyzing', 'transcribing', 'generating'].includes(t.status))
                              .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    const finishedTasks = tasks.filter(t => ['completed', 'failed'].includes(t.status))
                               .sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));

    if (youtubeReportsContainer && window.location.pathname.includes('youtube_report.html')) {
        const reportTasks = finishedTasks.filter(t => ['gemini_process', 'youtube_process_chain'].includes(t.type));
        youtubeReportsContainer.innerHTML = reportTasks.length > 0 ? reportTasks.map(getTaskHtml).join('') : `<p>尚無已完成的報告</p>`;

        const otherCompletedTasks = finishedTasks.filter(t => !['gemini_process', 'youtube_process_chain'].includes(t.type));
        if (completedTasksContainer) {
            completedTasksContainer.innerHTML = otherCompletedTasks.length > 0 ? otherCompletedTasks.map(getTaskHtml).join('') : `<p>尚無其他完成的任務</p>`;
        }
    } else if (completedTasksContainer) {
        completedTasksContainer.innerHTML = finishedTasks.length > 0 ? finishedTasks.map(getTaskHtml).join('') : `<p>尚無完成的任務</p>`;
    }

    if (ongoingTasksContainer) {
        ongoingTasksContainer.innerHTML = ongoingTasks.length > 0 ? ongoingTasks.map(getTaskHtml).join('') : `<p>暫無執行中任務</p>`;
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

// --- Modal Logic ---

function openMediaPreviewModal(task) {
    const modal = document.getElementById('preview-modal');
    const title = document.getElementById('modal-title');
    const body = modal.querySelector('.modal-body');
    const result = task.result || {};

    const mediaPath = result.source_path || result.output_path;
    if (!mediaPath) {
        showStatusMessage('找不到媒體檔案路徑。', true);
        return;
    }

    const isVideo = /\.(mp4|webm|mov)$/i.test(mediaPath);
    const isAudio = /\.(mp3|m4a|wav|flac|ogg)$/i.test(mediaPath);

    title.textContent = `預覽媒體: ${result.video_title || task.payload.original_filename}`;
    body.innerHTML = '';

    let mediaElement;
    if (isVideo) {
        mediaElement = document.createElement('video');
    } else if (isAudio) {
        mediaElement = document.createElement('audio');
    } else {
        body.innerHTML = `<p>不支援的媒體類型預覽。</p>`;
        modal.style.display = 'flex';
        return;
    }

    mediaElement.src = mediaPath;
    mediaElement.controls = true;
    mediaElement.autoplay = true;
    mediaElement.style.width = '100%';
    body.appendChild(mediaElement);

    modal.style.display = 'flex';
}

function openReportPreviewModal(task) {
    const modal = document.getElementById('preview-modal');
    const title = document.getElementById('modal-title');
    const body = modal.querySelector('.modal-body');
    const result = task.result || {};
    const outputPath = result.transcript_path || result.output_path || '';
    const fileType = outputPath.includes('.html') ? 'text/html' : 'text/plain';

    title.textContent = `預覽報告: ${ (result.video_title || task.payload.original_filename) }`;
    body.innerHTML = '正在載入預覽...';

    if (fileType === 'text/html') {
        const iframe = document.createElement('iframe');
        iframe.src = outputPath;
        iframe.style.width = '100%';
        iframe.style.height = '75vh';
        iframe.style.border = 'none';
        body.innerHTML = '';
        body.appendChild(iframe);
    } else {
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
        <p><strong>總執行時間:</strong> ${result.processing_duration_seconds?.toFixed(2) || 'N/A'} 秒</p>
        <p><strong>總 Token 消耗:</strong> ${result.total_tokens_used || 'N/A'} tokens</p>
        <p><strong>報告類型:</strong> ${ (result.output_path || '').includes('.html') ? 'HTML' : 'TXT'}</p>
        <p><strong>任務 ID:</strong> <small>${task.task_id}</small></p>
    `;
    modal.style.display = 'flex';
}

async function renameTask(taskId) {
    const task = globalState.tasks.find(t => t.task_id === taskId);
    if (!task) return;

    const currentName = task.result.video_title || task.payload.original_filename;
    const newName = prompt("請輸入新的檔案名稱 (不需包含副檔名):", currentName);

    if (newName && newName.trim() && newName.trim() !== currentName) {
        const sanitizedName = newName.trim().replace(/[\\/?%*:|"<>\x00-\x1F]/g, '');
        try {
            const response = await fetch(`/api/rename/${taskId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_filename: sanitizedName })
            });
            if (!response.ok) throw new Error((await response.json()).detail);
            showStatusMessage('檔案重新命名成功！', false);
            const tasks = await (await fetch('/api/tasks')).json();
            updateStateAndRender({ tasks });
        } catch (error) {
            showStatusMessage(`重新命名失敗: ${error.message}`, true);
        }
    }
}

async function sendToTranscriber(taskId) {
    const task = globalState.tasks.find(t => t.task_id === taskId);
    if (!task) return;

    const mediaPath = task.result.source_path || task.result.output_path;
    if (!mediaPath) {
        showStatusMessage('找不到媒體檔案路徑。', true);
        return;
    }

    showStatusMessage('正在準備檔案...', false, 2000);
    try {
        const response = await fetch(mediaPath);
        if (!response.ok) throw new Error('無法從伺服器獲取音訊檔案');
        const audioBlob = await response.blob();
        const filename = mediaPath.split('/').pop();
        const audioFile = new File([audioBlob], filename, { type: response.headers.get('Content-Type') });

        localStorage.setItem('fileToSend', JSON.stringify({
            name: audioFile.name,
            type: audioFile.type,
            size: audioFile.size
        }));

        const reader = new FileReader();
        reader.onload = (e) => {
            sessionStorage.setItem('fileToSend_data', e.target.result);
            window.location.href = '/static/transcribe.html';
        };
        reader.readAsDataURL(audioBlob);

    } catch (error) {
        showStatusMessage(`傳送至轉錄區失敗: ${error.message}`, true);
    }
}

function setupModalListeners() {
    const previewModal = document.getElementById('preview-modal');
    const detailsModal = document.getElementById('details-modal');

    const closeModal = (modal) => {
        if (!modal) return;
        modal.style.display = 'none';
        const mediaElement = modal.querySelector('video, audio');
        if (mediaElement) {
            mediaElement.pause();
            mediaElement.src = '';
        }
        const body = modal.querySelector('.modal-body');
        if (body) body.innerHTML = '';
    };

    document.getElementById('modal-close-btn')?.addEventListener('click', () => closeModal(previewModal));
    document.getElementById('details-modal-close-btn')?.addEventListener('click', () => closeModal(detailsModal));
    document.getElementById('details-modal-ok-btn')?.addEventListener('click', () => closeModal(detailsModal));

    previewModal?.addEventListener('click', (e) => e.target === previewModal && closeModal(previewModal));
    detailsModal?.addEventListener('click', (e) => e.target === detailsModal && closeModal(detailsModal));

    document.body.addEventListener('click', (e) => {
        const target = e.target.closest('button, a');
        if (!target) return;

        const taskId = target.dataset.taskId;
        if (!taskId) return;

        const task = globalState.tasks.find(t => t.task_id === taskId);
        if (!task) return;

        if (target.classList.contains('btn-preview')) {
            openReportPreviewModal(task);
        } else if (target.classList.contains('btn-details')) {
            openDetailsModal(task);
        } else if (target.classList.contains('btn-preview-media')) {
            openMediaPreviewModal(task);
        } else if (target.classList.contains('btn-rename')) {
            renameTask(taskId);
        } else if (target.classList.contains('btn-send-to-whisper')) {
            sendToTranscriber(taskId);
        }
    });
}


export const AppInitializer = {
    init: function(pageConfig = {}) {
        document.addEventListener('DOMContentLoaded', async () => {
            if (pageConfig.pageId) {
                setActiveNavButton(pageConfig.pageId);
            }
            setupWebSocket();
            setupModalListeners();
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
