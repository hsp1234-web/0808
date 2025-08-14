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

// src/frontend/components/YouTubeReporter.js
class YouTubeReporter {
  constructor(container, deps) {
    this.container = container;
    this.api = deps.api;
    this.showStatusMessage = deps.showStatusMessage;
    this.openPreviewModal = deps.openPreviewModal;
    this.logAction = deps.logAction;
    this.taskManager = deps.taskManager;
    this.completedReports = [];
  }
  init() {
    this.render();
    this.addEventListeners();
    this.initializeYouTubeTab();
  }
  render() {
    this.container.innerHTML = `
            <div id="youtube-report-tab" class="tab-content active">
                <div class="card">
                    <!-- 區域 1: API 金鑰管理 -->
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                        <h2>\uD83D\uDD11 Google API 金鑰管理</h2>
                        <a href="/static/prompts.html" target="_blank" style="font-weight: 500;">管理提示詞 &rarr;</a>
                    </div>
                    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 12px;">
                        <input type="password" id="api-key-input" placeholder="在此貼上您的 Google API 金鑰" style="flex-grow: 1; padding: 10px; border-radius: 6px; border: 1px solid #ccc;">
                        <button id="save-api-key-btn">儲存金鑰</button>
                        <button id="clear-api-key-btn" style="background-color: #6c757d;">清除金鑰</button>
                    </div>
                    <p id="api-key-status" style="margin-top: 0; font-weight: 500;">狀態: <span style="font-style: italic;">尚未提供金鑰</span></p>

                    <!-- 區域 2: YouTube 影片處理 -->
                    <h2 style="margin-top: 24px;">▶️ 輸入 YouTube 影片</h2>
                    <fieldset id="youtube-controls-fieldset">
                        <div id="youtube-link-list" class="flex-col" style="gap: 10px;">
                            <div class="youtube-link-row" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
                                <input type="text" class="youtube-url-input" placeholder="YouTube 影片網址" style="flex: 1 1 400px; padding: 10px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box;">
                                <input type="text" class="youtube-filename-input" placeholder="自訂檔名 (可選)" style="flex: 1 1 200px; padding: 10px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box;">
                                <button class="remove-youtube-row-btn" style="background-color: #dc3545; padding: 10px 15px; flex-shrink: 0; line-height: 1; font-size: 1.2em;">×</button>
                            </div>
                        </div>
                        <button id="add-youtube-row-btn" style="margin-top: 12px;">+ 新增一列</button>
                    </fieldset>
                </div>

                <!-- 區域 3: 參數控制區 -->
                <div class="card" style="margin-top: 24px;">
                    <h2>⚙️ 參數控制區</h2>
                    <fieldset id="youtube-params-fieldset" disabled>
                        <div class="grid-2-col">
                            <div>
                                <label><strong>任務選項</strong></label>
                                <div id="yt-tasks-group" style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px;">
                                    <label><input type="checkbox" name="yt-task" value="summary" checked> 重點摘要</label>
                                    <label><input type="checkbox" name="yt-task" value="transcript" checked> 詳細逐字稿</label>
                                    <label><input type="checkbox" name="yt-task" value="translate"> 翻譯為英文 (基於逐字稿)</label>
                                </div>
                            </div>
                            <div class="flex-col">
                                <div>
                                    <label for="gemini-model-select"><strong>AI 模型</strong></label>
                                    <select id="gemini-model-select">
                                        <option>等待從伺服器載入模型列表...</option>
                                    </select>
                                </div>
                                <div>
                                    <label for="yt-output-format-select"><strong>輸出格式</strong></label>
                                    <select id="yt-output-format-select">
                                        <option value="html">HTML 報告</option>
                                        <option value="txt">純文字 (.txt)</option>
                                    </select>
                                </div>
                            </div>
                        </div>
                    </fieldset>
                </div>

                <!-- 區域 4: 操作按鈕 -->
                <div style="text-align: center; margin-top: 24px; display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
                    <button id="download-audio-only-btn">\uD83C\uDFA7 僅下載音訊</button>
                    <button id="start-youtube-processing-btn" disabled>\uD83D\uDE80 分析影片 (Gemini)</button>
                </div>

                <!-- 區域 5: YouTube 報告瀏覽區 -->
                <div id="youtube-file-browser-container" class="card" style="margin-top: 24px;">
                    <h2>\uD83D\uDCCA YouTube 報告瀏覽區</h2>
                    <div id="youtube-file-browser" class="task-list" style="margin-top: 16px;">
                        <p id="no-youtube-report-msg">尚無已完成的報告</p>
                    </div>
                </div>
            </div>
        `;
    this.cacheDomElements();
  }
  cacheDomElements() {
    this.apiKeyInput = this.container.querySelector("#api-key-input");
    this.saveApiKeyBtn = this.container.querySelector("#save-api-key-btn");
    this.clearApiKeyBtn = this.container.querySelector("#clear-api-key-btn");
    this.apiKeyStatus = this.container.querySelector("#api-key-status");
    this.startYoutubeProcessingBtn = this.container.querySelector("#start-youtube-processing-btn");
    this.downloadAudioOnlyBtn = this.container.querySelector("#download-audio-only-btn");
    this.geminiModelSelect = this.container.querySelector("#gemini-model-select");
    this.addYoutubeRowBtn = this.container.querySelector("#add-youtube-row-btn");
    this.youtubeLinkList = this.container.querySelector("#youtube-link-list");
    this.youtubeParamsFieldset = this.container.querySelector("#youtube-params-fieldset");
    this.ytOutputFormatSelect = this.container.querySelector("#yt-output-format-select");
    this.youtubeFileBrowser = this.container.querySelector("#youtube-file-browser");
    this.noYoutubeReportMsg = this.container.querySelector("#no-youtube-report-msg");
  }
  addEventListeners() {
    this.saveApiKeyBtn.addEventListener("click", () => {
      const apiKey = this.apiKeyInput.value.trim();
      this.logAction("click-save-api-key");
      if (apiKey) {
        localStorage.setItem("googleApiKey", apiKey);
        this.validateApiKey(apiKey);
      } else {
        this.showStatusMessage("API 金鑰不能為空", true);
      }
    });
    this.clearApiKeyBtn.addEventListener("click", () => {
      this.logAction("click-clear-api-key");
      localStorage.removeItem("googleApiKey");
      this.apiKeyInput.value = "";
      this.updateApiKeyUI("not_provided");
      this.geminiModelSelect.innerHTML = "<option>提供有效金鑰後將載入模型</option>";
    });
    this.addYoutubeRowBtn.addEventListener("click", () => this.addNewYoutubeRow());
    this.youtubeLinkList.addEventListener("click", (e) => {
      if (e.target && e.target.classList.contains("remove-youtube-row-btn")) {
        this.logAction("click-remove-youtube-row");
        if (this.youtubeLinkList.querySelectorAll(".youtube-link-row").length > 1) {
          e.target.closest(".youtube-link-row").remove();
        } else {
          this.showStatusMessage("至少需要保留一列。", true, 3000);
        }
      }
    });
    this.youtubeLinkList.addEventListener("input", (e) => {
      if (e.target && e.target.classList.contains("youtube-filename-input")) {
        e.target.value = this.sanitizeFilename(e.target.value);
      }
    });
    this.downloadAudioOnlyBtn.addEventListener("click", () => this.processYoutubeRequest(true));
    this.startYoutubeProcessingBtn.addEventListener("click", () => this.processYoutubeRequest(false));
  }
  initializeYouTubeTab() {
    this.logAction("initialize-youtube-tab");
    const storedApiKey = localStorage.getItem("googleApiKey");
    if (storedApiKey) {
      this.apiKeyInput.value = storedApiKey;
      this.validateApiKey(storedApiKey);
    } else {
      this.updateApiKeyUI("not_provided");
      this.geminiModelSelect.innerHTML = "<option>提供有效金鑰後將載入模型</option>";
    }
  }
  updateApiKeyUI(state, message) {
    const statusSpan = this.apiKeyStatus.querySelector("span");
    statusSpan.style.color = "inherit";
    statusSpan.style.fontStyle = "normal";
    const isValid = state === "valid";
    this.startYoutubeProcessingBtn.disabled = !isValid;
    this.youtubeParamsFieldset.disabled = !isValid;
    switch (state) {
      case "valid":
        statusSpan.textContent = message || "驗證成功";
        statusSpan.style.color = "var(--status-green)";
        this.startYoutubeProcessingBtn.title = "";
        break;
      case "invalid":
        statusSpan.textContent = message || "驗證失敗";
        statusSpan.style.color = "#dc3545";
        this.startYoutubeProcessingBtn.title = "請提供有效的 API 金鑰以啟用此功能";
        break;
      case "validating":
        statusSpan.textContent = message || "正在驗證中...";
        statusSpan.style.fontStyle = "italic";
        break;
      case "not_provided":
      default:
        statusSpan.textContent = message || "尚未提供金鑰";
        statusSpan.style.fontStyle = "italic";
        this.startYoutubeProcessingBtn.title = "請提供有效的 API 金鑰以啟用此功能";
        break;
    }
  }
  async validateApiKey(apiKey) {
    if (!apiKey) {
      this.updateApiKeyUI("not_provided");
      return;
    }
    this.updateApiKeyUI("validating");
    try {
      const result = await this.api.youtube.validateApiKey(apiKey);
      this.updateApiKeyUI("valid", "金鑰有效，Gemini 功能已啟用");
      this.loadGeminiModels();
    } catch (error) {
      console.error("API Key validation error:", JSON.stringify(error, null, 2));
      this.updateApiKeyUI("invalid", error.detail || "金鑰無效或發生未知錯誤");
    }
  }
  async loadGeminiModels() {
    try {
      const modelsData = await this.api.youtube.getModels();
      this.geminiModelSelect.innerHTML = "";
      modelsData.models.forEach((model) => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.name;
        this.geminiModelSelect.appendChild(option);
      });
      this.logAction("load-gemini-models-success");
    } catch (error) {
      console.error("載入 Gemini 模型時出錯:", error);
      this.logAction("load-gemini-models-failed");
      this.geminiModelSelect.innerHTML = `<option>${error.message}</option>`;
    }
  }
  addNewYoutubeRow() {
    this.logAction("click-add-youtube-row");
    const firstRow = this.youtubeLinkList.querySelector(".youtube-link-row");
    if (!firstRow)
      return;
    const newRow = firstRow.cloneNode(true);
    newRow.querySelector(".youtube-url-input").value = "";
    newRow.querySelector(".youtube-filename-input").value = "";
    this.youtubeLinkList.appendChild(newRow);
  }
  sanitizeFilename(filename) {
    return filename.replace(/[\\/?%*:|"<>\x00-\x1F]/g, "");
  }
  async processYoutubeRequest(downloadOnly = false) {
    const action = downloadOnly ? "click-download-audio-only" : "click-start-youtube-processing";
    this.logAction(action);
    const rows = this.youtubeLinkList.querySelectorAll(".youtube-link-row");
    const requests = Array.from(rows).map((row) => {
      const urlInput = row.querySelector(".youtube-url-input");
      const filenameInput = row.querySelector(".youtube-filename-input");
      return {
        url: urlInput.value.trim(),
        filename: filenameInput.value.trim()
      };
    }).filter((req) => req.url);
    if (requests.length === 0) {
      this.showStatusMessage("請輸入至少一個有效的 YouTube 網址。", true);
      return;
    }
    const selectedTasks = Array.from(this.container.querySelectorAll('input[name="yt-task"]:checked')).map((cb) => cb.value);
    if (!downloadOnly && selectedTasks.length === 0) {
      this.showStatusMessage("請至少選擇一個 AI 分析任務。", true);
      return;
    }
    const button = downloadOnly ? this.downloadAudioOnlyBtn : this.startYoutubeProcessingBtn;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "正在建立任務...";
    try {
      const payload = {
        requests,
        model: this.geminiModelSelect.value,
        download_only: downloadOnly,
        tasks: selectedTasks.join(","),
        output_format: this.ytOutputFormatSelect.value
      };
      const result = await this.api.youtube.process(payload);
      result.tasks.forEach((task) => {
        this.taskManager.startTask(task);
      });
      const allRows = this.youtubeLinkList.querySelectorAll(".youtube-link-row");
      allRows.forEach((row, index) => {
        if (index === 0) {
          row.querySelector(".youtube-url-input").value = "";
          row.querySelector(".youtube-filename-input").value = "";
        } else {
          row.remove();
        }
      });
    } catch (error) {
      this.showStatusMessage(`處理 YouTube 任務時發生錯誤: ${error.message}`, true);
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }
  addYoutubeReportToList(payload) {
    if (this.noYoutubeReportMsg && this.noYoutubeReportMsg.style.display !== "none") {
      this.noYoutubeReportMsg.style.display = "none";
    }
    const result = payload.result || {};
    const taskId = payload.task_id;
    const videoTitle = result.video_title || "無標題報告";
    const outputPath = result.output_path || "";
  }
}
export {
  YouTubeReporter
};
