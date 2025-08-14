/**
 * TaskList 組件
 *
 * 負責渲染和管理「進行中」和「已完成」的任務列表，並處理即時更新。
 */
export class TaskList {
    /**
     * @param {HTMLElement} element - 要將此組件渲染到的容器元素。
     * @param {object} options - 組件選項。
     * @param {function} options.showStatusMessage - 用於顯示全域狀態訊息的函式。
     * @param {function} options.openPreviewModal - 用於開啟預覽彈窗的函式。
     */
    constructor(element, options) {
        this.container = element;
        // 外部傳入的輔助函式，用於解耦
        this.showStatusMessage = options.showStatusMessage || console.log;
        this.openPreviewModal = options.openPreviewModal || console.log;

        this.state = {
            ongoing: [],
            completed: [],
        };
        this.taskElements = new Map(); // 用於追蹤每個任務的 DOM 元素
    }

    /**
     * 渲染組件的 HTML 骨架和內容。
     * 這個方法會根據當前狀態重新繪製整個組件。
     */
    render() {
        // 1. 建立 HTML 骨架
        this.container.innerHTML = `
            <div class="grid-2-col">
                <div class="card">
                    <h2>🔄 進行中任務</h2>
                    <div id="ongoing-tasks" class="task-list"></div>
                </div>
                <div class="card">
                    <h2>✅ 已完成任務</h2>
                    <div id="completed-tasks" class="task-list"></div>
                </div>
            </div>
        `;

        // 2. 根據狀態填充列表
        this._renderTaskList(
            this.state.ongoing,
            this.container.querySelector('#ongoing-tasks'),
            '暫無執行中任務',
            'no-ongoing-task-msg'
        );
        this._renderTaskList(
            this.state.completed,
            this.container.querySelector('#completed-tasks'),
            '尚無完成的任務',
            'no-completed-task-msg'
        );
    }

    /**
     * 根據提供的資料和目標元素來渲染一個任務列表（例如「進行中」或「已完成」）。
     * @param {Array<object>} tasks - 要渲染的任務物件陣列。
     * @param {HTMLElement} targetElement - 任務項目要被附加到的容器元素。
     * @param {string} noTasksMessage - 當沒有任務時要顯示的訊息。
     * @param {string} noTasksMessageId - "無任務" 訊息段落的 DOM ID。
     */
    _renderTaskList(tasks, targetElement, noTasksMessage, noTasksMessageId) {
        if (!targetElement) return;

        // 清空現有內容
        targetElement.innerHTML = '';

        // 注意：這是一個簡化的方法，用於清除此重構中的任務元素。
        // 在更複雜的應用中，您可能需要更精細地管理 taskElements Map。
        this.taskElements.clear();

        if (tasks && tasks.length > 0) {
            tasks.forEach(task => {
                const taskElement = this._createTaskElement(task);
                targetElement.appendChild(taskElement);
                this.taskElements.set(task.id, taskElement);
            });
        } else {
            // 如果沒有任務，顯示對應的訊息
            targetElement.innerHTML = `<p id="${noTasksMessageId}" class="text-gray-500 text-center">${noTasksMessage}</p>`;
        }
    }

    /**
     * 根據單一任務物件建立其 DOM 元素。
     * @param {object} task - 任務物件。
     * @returns {HTMLElement}
     */
    _createTaskElement(task) {
        const taskElement = document.createElement('div');
        taskElement.className = 'task-item';
        taskElement.dataset.taskId = task.id;

        // JULES'S FIX: 優先使用 payload 中的原始檔名或 URL
        const displayName = task.payload?.original_filename || task.payload?.url || task.id;
        const taskType = task.type || '未知';
        const icon = this._getIconForFile(task.result?.output_path || '');

        taskElement.innerHTML = `
            <div class="flex-grow overflow-hidden mr-2.5 min-w-0">
                <span class="task-filename" title="${displayName}">
                    <span class="file-icon mr-2">${icon}</span>
                    ${displayName} (${taskType})
                </span>
                <div class="task-progress-container bg-gray-200 rounded h-2 mt-1.5 hidden">
                    <div class="task-progress-bar h-full bg-btn-bg rounded w-0 transition-width duration-200"></div>
                </div>
            </div>
            <span class="task-status flex-shrink-0 text-right min-w-[120px]"></span>`;

        this._updateTaskElement(taskElement, task);
        return taskElement;
    }

    /**
     * 更新現有的任務 DOM 元素。
     * @param {HTMLElement} taskElement - 要更新的 DOM 元素。
     * @param {object} task - 最新的任務物件。
     */
    _updateTaskElement(taskElement, task) {
        const statusSpan = taskElement.querySelector('.task-status');
        const progressContainer = taskElement.querySelector('.task-progress-container');
        const progressBar = taskElement.querySelector('.task-progress-bar');

        const status = task.status || '未知';
        const result = task.result || {};

        statusSpan.className = 'task-status'; // Reset classes

        if (status === 'completed' || status === 'failed') {
            if (progressContainer) progressContainer.style.display = 'none';

            if (status === 'completed') {
                statusSpan.innerHTML = '';
                statusSpan.classList.add('status-completed');
                const buttonGroup = this._createActionButtons(task);
                statusSpan.appendChild(buttonGroup);
            } else { // failed
                statusSpan.textContent = `❌ 失敗`;
                statusSpan.title = result.error || '未知錯誤';
                statusSpan.classList.add('status-failed');
            }
        } else {
            // 進行中任務的邏輯
            statusSpan.textContent = result.message || status;
            if (progressContainer) progressContainer.style.display = 'block';
            if (result.progress && progressBar) {
                progressBar.style.width = `${result.progress}%`;
            }
             if (status === 'downloading') statusSpan.classList.add('status-downloading');
             if (status === 'processing') statusSpan.classList.add('status-processing');
        }
    }

    /**
     * 從 API 載入任務歷史紀錄，並更新狀態與 UI。
     */
    async loadTaskHistory() {
        try {
            const response = await fetch('/api/tasks');
            if (!response.ok) throw new Error(`無法獲取任務歷史： ${response.statusText}`);

            const tasks = await response.json();

            this.state.ongoing = tasks.filter(t => t.status !== 'completed' && t.status !== 'failed');
            this.state.completed = tasks.filter(t => t.status === 'completed' || t.status === 'failed');

            this.render(); // 用載入的資料重新渲染整個組件

        } catch (error) {
            console.error('載入任務歷史時發生錯誤:', error);
            this.container.innerHTML = `<p style="color: red;">載入任務列表失敗: ${error.message}</p>`;
        }
    }

    /**
     * 公開方法，用於處理來自 WebSocket 的即時任務更新。
     * @param {object} payload - WebSocket 訊息的 payload。
     */
    handleTaskUpdate(payload) {
        const taskId = payload.task_id;
        if (!taskId) return;

        let task = this.state.ongoing.find(t => t.id === taskId) || this.state.completed.find(t => t.id === taskId);
        let taskElement = this.taskElements.get(taskId);

        const ongoingContainer = this.container.querySelector('#ongoing-tasks');
        const completedContainer = this.container.querySelector('#completed-tasks');

        if (task) {
            // 更新現有任務的狀態
            task.status = payload.status || task.status;
            // 合併 result，新的 payload 會覆蓋舊的
            task.result = { ...task.result, ...payload };
        } else {
            // 這是個新任務
            task = {
                id: taskId,
                status: payload.status,
                payload: { original_filename: payload.filename, url: payload.url },
                result: payload,
                type: payload.task_type || '未知'
            };
            this.state.ongoing.push(task);

            // 如果是第一個進行中任務，移除 "無任務" 訊息
            if (ongoingContainer.querySelector('p')) {
                ongoingContainer.innerHTML = '';
            }
            taskElement = this._createTaskElement(task);
            ongoingContainer.appendChild(taskElement);
            this.taskElements.set(taskId, taskElement);
        }

        // 更新 UI
        if (taskElement) {
            this._updateTaskElement(taskElement, task);
        }

        // 檢查是否需要移動列表
        const isCompleted = task.status === 'completed' || task.status === 'failed';
        const wasInOngoing = Array.from(ongoingContainer.children).some(el => el === taskElement);

        if (isCompleted && wasInOngoing) {
            this.state.ongoing = this.state.ongoing.filter(t => t.id !== taskId);
            this.state.completed.push(task);

            // 如果是第一個完成的任務，移除 "無任務" 訊息
            if (completedContainer.querySelector('p')) {
                completedContainer.innerHTML = '';
            }
            completedContainer.appendChild(taskElement); // 移動 DOM 元素
        }
    }

    /**
     * 初始化組件。
     */
    async init() {
        this.render(); // 渲染骨架
        await this.loadTaskHistory(); // 等待歷史紀錄載入並完成初次渲染
    }

    // --- Helper methods copied and adapted from mp3.html ---

    _getIconForFile(outputPath) {
        if (!outputPath || typeof outputPath !== 'string') return '📁';
        if (outputPath.endsWith('.mp4')) return '🎥';
        if (['.mp3', '.m4a', '.wav', '.flac', '.ogg'].some(ext => outputPath.endsWith(ext))) return '🎵';
        if (outputPath.endsWith('.html')) return '📄';
        if (outputPath.endsWith('.txt')) return '📝';
        return '📁';
    }

    _createActionButtons(task) {
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'task-actions';

        const result = task.result || {};
        const outputPath = result.output_path || result.transcript_path || '';
        if (!outputPath) return buttonGroup;

        const title = result.video_title || result.original_filename || task.payload?.original_filename || 'Untitled';
        const extension = outputPath.substring(outputPath.lastIndexOf('.'));
        const fileMimeTypes = {
            '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4',
            '.wav': 'audio/wav', '.flac': 'audio/flac', '.html': 'text/html',
            '.txt': 'text/plain'
        };
        const mimeType = fileMimeTypes[extension] || 'application/octet-stream';

        const isMedia = mimeType.startsWith('video/') || mimeType.startsWith('audio/');
        const isReport = mimeType === 'text/html' || (mimeType === 'text/plain' && outputPath.includes('/transcripts/'));

        if (isMedia || isReport) {
            const previewBtn = this._createButton('預覽', 'btn-preview', (e) => {
                e.preventDefault();
                this.openPreviewModal(outputPath, title, mimeType, task.id);
            });
            buttonGroup.appendChild(previewBtn);
        }

        const downloadBtn = document.createElement('a');
        downloadBtn.href = `/api/download/${task.id}`;
        downloadBtn.className = 'btn-download';
        downloadBtn.textContent = '下載';
        downloadBtn.download = `${title}${extension}`;
        buttonGroup.appendChild(downloadBtn);

        return buttonGroup;
    }

    _createButton(text, className, onClick) {
        const btn = document.createElement('a');
        btn.href = '#';
        btn.className = className;
        btn.textContent = text;
        btn.addEventListener('click', onClick);
        return btn;
    }
}
