// src/frontend/components/TaskList.js
class TaskList {
  constructor(element, options) {
    this.container = element;
    this.showStatusMessage = options.showStatusMessage || console.log;
    this.openPreviewModal = options.openPreviewModal || console.log;
    this.state = {
      ongoing: [],
      completed: []
    };
    this.taskElements = new Map;
  }
  render() {
    this.container.innerHTML = `
            <div class="grid-2-col">
                <div class="card">
                    <h2>\uD83D\uDD04 進行中任務</h2>
                    <div id="ongoing-tasks" class="task-list"></div>
                </div>
                <div class="card">
                    <h2>✅ 已完成任務</h2>
                    <div id="completed-tasks" class="task-list"></div>
                </div>
            </div>
        `;
    this._renderTaskList(this.state.ongoing, this.container.querySelector("#ongoing-tasks"), "暫無執行中任務", "no-ongoing-task-msg");
    this._renderTaskList(this.state.completed, this.container.querySelector("#completed-tasks"), "尚無完成的任務", "no-completed-task-msg");
  }
  _renderTaskList(tasks, targetElement, noTasksMessage, noTasksMessageId) {
    if (!targetElement)
      return;
    targetElement.innerHTML = "";
    this.taskElements.clear();
    if (tasks && tasks.length > 0) {
      tasks.forEach((task) => {
        const taskElement = this._createTaskElement(task);
        targetElement.appendChild(taskElement);
        this.taskElements.set(task.id, taskElement);
      });
    } else {
      targetElement.innerHTML = `<p id="${noTasksMessageId}">${noTasksMessage}</p>`;
    }
  }
  _createTaskElement(task) {
    const taskElement = document.createElement("div");
    taskElement.className = "task-item";
    taskElement.dataset.taskId = task.id;
    const displayName = task.payload?.original_filename || task.payload?.url || task.id;
    const taskType = task.type || "未知";
    const icon = this._getIconForFile(task.result?.output_path || "");
    taskElement.innerHTML = `
            <div style="flex-grow: 1; overflow: hidden; margin-right: 10px; min-width: 0;">
                <span class="task-filename" title="${displayName}">
                    <span class="file-icon" style="margin-right: 8px;">${icon}</span>
                    ${displayName} (${taskType})
                </span>
                <div class="task-progress-container" style="background-color: #e9ecef; border-radius: 4px; height: 8px; margin-top: 5px; display: none;">
                    <div class="task-progress-bar" style="width: 0%; height: 100%; background-color: var(--button-bg-color); border-radius: 4px; transition: width 0.2s;"></div>
                </div>
            </div>
            <span class="task-status" style="flex-shrink: 0; text-align: right; min-width: 120px;"></span>`;
    this._updateTaskElement(taskElement, task);
    return taskElement;
  }
  _updateTaskElement(taskElement, task) {
    const statusSpan = taskElement.querySelector(".task-status");
    const progressContainer = taskElement.querySelector(".task-progress-container");
    const progressBar = taskElement.querySelector(".task-progress-bar");
    const status = task.status || "未知";
    const result = task.result || {};
    statusSpan.className = "task-status";
    if (status === "completed" || status === "failed") {
      if (progressContainer)
        progressContainer.style.display = "none";
      if (status === "completed") {
        statusSpan.innerHTML = "";
        statusSpan.classList.add("status-completed");
        const buttonGroup = this._createActionButtons(task);
        statusSpan.appendChild(buttonGroup);
      } else {
        statusSpan.textContent = `❌ 失敗`;
        statusSpan.title = result.error || "未知錯誤";
        statusSpan.classList.add("status-failed");
      }
    } else {
      statusSpan.textContent = result.message || status;
      if (progressContainer)
        progressContainer.style.display = "block";
      if (result.progress && progressBar) {
        progressBar.style.width = `${result.progress}%`;
      }
      if (status === "downloading")
        statusSpan.classList.add("status-downloading");
      if (status === "processing")
        statusSpan.classList.add("status-processing");
    }
  }
  async loadTaskHistory() {
    try {
      const response = await fetch("/api/tasks");
      if (!response.ok)
        throw new Error(`無法獲取任務歷史： ${response.statusText}`);
      const tasks = await response.json();
      this.state.ongoing = tasks.filter((t) => t.status !== "completed" && t.status !== "failed");
      this.state.completed = tasks.filter((t) => t.status === "completed" || t.status === "failed");
      this.render();
    } catch (error) {
      console.error("載入任務歷史時發生錯誤:", error);
      this.container.innerHTML = `<p style="color: red;">載入任務列表失敗: ${error.message}</p>`;
    }
  }
  handleTaskUpdate(payload) {
    const taskId = payload.task_id;
    if (!taskId)
      return;
    let task = this.state.ongoing.find((t) => t.id === taskId) || this.state.completed.find((t) => t.id === taskId);
    let taskElement = this.taskElements.get(taskId);
    const ongoingContainer = this.container.querySelector("#ongoing-tasks");
    const completedContainer = this.container.querySelector("#completed-tasks");
    if (task) {
      task.status = payload.status || task.status;
      task.result = { ...task.result, ...payload };
    } else {
      task = {
        id: taskId,
        status: payload.status,
        payload: { original_filename: payload.filename, url: payload.url },
        result: payload,
        type: payload.task_type || "未知"
      };
      this.state.ongoing.push(task);
      if (ongoingContainer.querySelector("p")) {
        ongoingContainer.innerHTML = "";
      }
      taskElement = this._createTaskElement(task);
      ongoingContainer.appendChild(taskElement);
      this.taskElements.set(taskId, taskElement);
    }
    if (taskElement) {
      this._updateTaskElement(taskElement, task);
    }
    const isCompleted = task.status === "completed" || task.status === "failed";
    const wasInOngoing = Array.from(ongoingContainer.children).some((el) => el === taskElement);
    if (isCompleted && wasInOngoing) {
      this.state.ongoing = this.state.ongoing.filter((t) => t.id !== taskId);
      this.state.completed.push(task);
      if (completedContainer.querySelector("p")) {
        completedContainer.innerHTML = "";
      }
      completedContainer.appendChild(taskElement);
    }
  }
  async init() {
    this.render();
    await this.loadTaskHistory();
  }
  _getIconForFile(outputPath) {
    if (!outputPath || typeof outputPath !== "string")
      return "\uD83D\uDCC1";
    if (outputPath.endsWith(".mp4"))
      return "\uD83C\uDFA5";
    if ([".mp3", ".m4a", ".wav", ".flac", ".ogg"].some((ext) => outputPath.endsWith(ext)))
      return "\uD83C\uDFB5";
    if (outputPath.endsWith(".html"))
      return "\uD83D\uDCC4";
    if (outputPath.endsWith(".txt"))
      return "\uD83D\uDCDD";
    return "\uD83D\uDCC1";
  }
  _createActionButtons(task) {
    const buttonGroup = document.createElement("div");
    buttonGroup.className = "task-actions";
    const result = task.result || {};
    const outputPath = result.output_path || result.transcript_path || "";
    if (!outputPath)
      return buttonGroup;
    const title = result.video_title || result.original_filename || task.payload?.original_filename || "Untitled";
    const extension = outputPath.substring(outputPath.lastIndexOf("."));
    const fileMimeTypes = {
      ".mp4": "video/mp4",
      ".mp3": "audio/mpeg",
      ".m4a": "audio/mp4",
      ".wav": "audio/wav",
      ".flac": "audio/flac",
      ".html": "text/html",
      ".txt": "text/plain"
    };
    const mimeType = fileMimeTypes[extension] || "application/octet-stream";
    const isMedia = mimeType.startsWith("video/") || mimeType.startsWith("audio/");
    const isReport = mimeType === "text/html" || mimeType === "text/plain" && outputPath.includes("/transcripts/");
    if (isMedia || isReport) {
      const previewBtn = this._createButton("預覽", "btn-preview", (e) => {
        e.preventDefault();
        this.openPreviewModal(outputPath, title, mimeType, task.id);
      });
      buttonGroup.appendChild(previewBtn);
    }
    const downloadBtn = document.createElement("a");
    downloadBtn.href = `/api/download/${task.id}`;
    downloadBtn.className = "btn-download";
    downloadBtn.textContent = "下載";
    downloadBtn.download = `${title}${extension}`;
    buttonGroup.appendChild(downloadBtn);
    return buttonGroup;
  }
  _createButton(text, className, onClick) {
    const btn = document.createElement("a");
    btn.href = "#";
    btn.className = className;
    btn.textContent = text;
    btn.addEventListener("click", onClick);
    return btn;
  }
}
export {
  TaskList
};
