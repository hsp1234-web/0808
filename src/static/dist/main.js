// src/frontend/components/FileBrowser.js
class FileBrowser {
  constructor(element) {
    this.container = element;
  }
  render() {
    this.container.innerHTML = `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>\uD83D\uDCC1 檔案總管 (Uploads)</h2>
                    <button id="reload-file-browser-btn">\uD83D\uDD04 重新整理</button>
                </div>
                <div id="file-browser-list" style="margin-top: 16px; min-height: 100px; border: 1px solid #eee; padding: 10px;">
                    <p id="file-browser-loading-msg">正在載入檔案列表...</p>
                </div>
            </div>
        `;
  }
  addEventListeners() {
    const reloadBtn = this.container.querySelector("#reload-file-browser-btn");
    if (reloadBtn) {
      reloadBtn.addEventListener("click", () => {
        console.log("重新整理按鈕被點擊！");
        this.loadFileBrowser();
      });
    }
  }
  async loadFileBrowser() {
    console.log("開始載入檔案列表...");
    const listElement = this.container.querySelector("#file-browser-list");
    if (!listElement)
      return;
    listElement.innerHTML = "<p>正在載入檔案列表...</p>";
    setTimeout(() => {
      listElement.innerHTML = "<p>檔案列表將會顯示在這裡。</p>";
    }, 1000);
  }
  init() {
    this.render();
    this.addEventListeners();
    this.loadFileBrowser();
  }
}

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

// src/frontend/components/LocalTranscriber.js
class LocalTranscriber {
  constructor(element, services) {
    this.container = element;
    this.showStatusMessage = services.showStatusMessage;
    this.socket = services.socket;
    this.logAction = services.logAction;
    this.updateModelDisplay = services.updateModelDisplay;
    this.uploadedFiles = [];
  }
  render() {
    this.container.innerHTML = `
            <div>
                <div class="grid-2-col">
                    <div class="card flex-col">
                        <h2>⚙️ 步驟 1: 選項 (Whisper 模型)</h2>
                        <div>
                            <label for="model-select">模型大小</label>
                            <select id="model-select">
                                <option value="tiny" selected>Tiny (最快)</option>
                                <option value="base">Base</option>
                                <option value="small">Small</option>
                                <option value="medium">Medium (建議)</option>
                                <option value="large-v2">Large-v2 (準確)</option>
                                <option value="large-v3">Large-v3 (最準確)</option>
                            </select>
                        </div>
                        <div>
                            <label for="language-select">轉錄語言</label>
                            <select id="language-select">
                                <option value="zh">繁體中文</option>
                                <option value="en">英文</option>
                            </select>
                        </div>
                        <div>
                            <label for="beam-size-input" style="display: block; margin-bottom: 4px;">光束大小 (Beam Size)</label>
                            <input type="number" id="beam-size-input" value="1" min="1" max="10" style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box;">
                            <small style="font-size: 0.8em; color: #666;">建議值為 5。較大的值可能更準確但較慢。</small>
                        </div>
                        <button id="confirm-settings-btn">✓ 確認設定</button>
                        <!-- 模型下載進度條 -->
                        <div id="model-progress-container" class="progress-container hidden" style="margin-top: 10px;">
                            <div id="model-progress-bar" class="progress-bar"></div>
                            <span id="model-progress-text" class="progress-text"></span>
                        </div>
                    </div>
                    <div class="card flex-col">
                        <h2>\uD83D\uDCE4 步驟 2: 上傳檔案</h2>
                        <label for="file-input" class="file-drop-zone">
                            點擊此處選擇檔案
                        </label>
                        <input id="file-input" type="file" multiple class="hidden">
                        <div id="file-list" style="min-height: 50px;"></div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 24px;">
                    <button id="start-processing-btn" disabled>✨ 請先選擇檔案</button>
                </div>
            </div>
        `;
  }
  addEventListeners() {
    const fileInput = this.container.querySelector("#file-input");
    const fileDropZone = this.container.querySelector(".file-drop-zone");
    const confirmBtn = this.container.querySelector("#confirm-settings-btn");
    const startBtn = this.container.querySelector("#start-processing-btn");
    const modelSelect = this.container.querySelector("#model-select");
    fileInput.addEventListener("change", () => {
      this.logAction("change-file-input");
      const newFiles = Array.from(fileInput.files);
      this.addFiles(newFiles);
      fileInput.value = "";
    });
    fileDropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      fileDropZone.style.backgroundColor = "#f0f8ff";
      fileDropZone.style.borderColor = "var(--button-bg-color)";
    });
    fileDropZone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      fileDropZone.style.backgroundColor = "transparent";
      fileDropZone.style.borderColor = "#ccc";
    });
    fileDropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      fileDropZone.style.backgroundColor = "transparent";
      fileDropZone.style.borderColor = "#ccc";
      this.logAction("drop-file");
      const droppedFiles = Array.from(e.dataTransfer.files);
      this.addFiles(droppedFiles);
    });
    confirmBtn.addEventListener("click", () => {
      const model = modelSelect.value;
      this.logAction("click-confirm-settings", model);
      this.updateModelDisplay(model);
      confirmBtn.disabled = true;
      this.showModelProgress(`正在請求 ${model} 模型...`);
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "DOWNLOAD_MODEL", payload: { model } }));
      } else {
        this.showStatusMessage("WebSocket 未連線，無法下載模型。", true);
        this.showModelProgress("連線失敗", true);
        confirmBtn.disabled = false;
      }
    });
    startBtn.addEventListener("click", () => this.startProcessing());
    this.container.querySelector("#file-list").addEventListener("click", (e) => {
      if (e.target && e.target.classList.contains("remove-file-btn")) {
        const indexToRemove = parseInt(e.target.dataset.index, 10);
        this.logAction("click-remove-file", this.uploadedFiles[indexToRemove].name);
        this.uploadedFiles.splice(indexToRemove, 1);
        this.updateFileDisplay();
      }
    });
  }
  addFiles(newFiles) {
    newFiles.forEach((newFile) => {
      if (!this.uploadedFiles.some((existingFile) => existingFile.name === newFile.name)) {
        this.uploadedFiles.push(newFile);
      }
    });
    this.updateFileDisplay();
  }
  updateFileDisplay() {
    const fileListDisplay = this.container.querySelector("#file-list");
    const startBtn = this.container.querySelector("#start-processing-btn");
    if (!fileListDisplay || !startBtn)
      return;
    if (this.uploadedFiles.length === 0) {
      fileListDisplay.innerHTML = '<p style="color: #666; text-align: center;">尚未選擇任何檔案</p>';
    } else {
      fileListDisplay.innerHTML = this.uploadedFiles.map((file, index) => `
                <div class="task-item">
                    <span class="task-filename">${file.name}</span>
                    <button data-index="${index}" class="remove-file-btn" style="background-color: #dc3545; padding: 3px 8px; font-size: 0.8em;">移除</button>
                </div>
            `).join("");
    }
    startBtn.disabled = this.uploadedFiles.length === 0;
    startBtn.textContent = this.uploadedFiles.length > 0 ? `✨ 開始處理 ${this.uploadedFiles.length} 個檔案` : "✨ 請先選擇檔案";
  }
  handleModelDownloadStatus(payload) {
    if (payload.status === "downloading") {
      const percent = payload.percent || 0;
      this.showModelProgress(`下載中 (${payload.description || "..."})`, false, percent);
    } else if (payload.status === "completed") {
      this.showModelProgress("下載完成", false, 100);
      this.container.querySelector("#confirm-settings-btn").disabled = false;
    } else if (payload.status === "failed") {
      this.showModelProgress(`下載失敗: ${payload.error}`, true, 100);
      this.container.querySelector("#confirm-settings-btn").disabled = false;
    }
  }
  showModelProgress(text, isError = false, percent = 0) {
    const modelProgressContainer = this.container.querySelector("#model-progress-container");
    const modelProgressBar = this.container.querySelector("#model-progress-bar");
    const modelProgressText = this.container.querySelector("#model-progress-text");
    modelProgressContainer.classList.remove("hidden");
    modelProgressText.textContent = text;
    modelProgressBar.style.width = `${percent}%`;
    modelProgressBar.style.backgroundColor = isError ? "#dc3545" : "var(--button-bg-color)";
  }
  async startProcessing() {
    if (this.uploadedFiles.length === 0)
      return;
    this.logAction("click-start-processing", `files_count: ${this.uploadedFiles.length}`);
    const startBtn = this.container.querySelector("#start-processing-btn");
    startBtn.disabled = true;
    startBtn.textContent = "正在建立任務...";
    const modelSelect = this.container.querySelector("#model-select");
    const languageSelect = this.container.querySelector("#language-select");
    const beamSizeInput = this.container.querySelector("#beam-size-input");
    for (const file of this.uploadedFiles) {
      const formData = new FormData;
      formData.append("file", file);
      formData.append("model_size", modelSelect.value);
      formData.append("language", languageSelect.value);
      formData.append("beam_size", beamSizeInput.value);
      try {
        const response = await fetch("/api/transcribe", { method: "POST", body: formData });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "上傳失敗");
        }
        const result = await response.json();
        const tasks = Array.isArray(result.tasks) ? result.tasks : [result];
        tasks.forEach((task) => {
          if (this.socket && task.type === "transcribe") {
            this.socket.send(JSON.stringify({ type: "START_TRANSCRIPTION", payload: { task_id: task.task_id } }));
          }
        });
      } catch (error) {
        this.showStatusMessage(`處理檔案 ${file.name} 時發生錯誤: ${error.message}`, true);
      }
    }
    this.uploadedFiles = [];
    this.updateFileDisplay();
  }
  init() {
    this.render();
    this.addEventListeners();
    this.updateFileDisplay();
  }
}

// src/frontend/components/MediaDownloader.js
class MediaDownloader {
  constructor(element, services) {
    this.container = element;
    this.showStatusMessage = services.showStatusMessage;
    this.socket = services.socket;
    this.logAction = services.logAction;
    this.createNewTaskElement = services.createNewTaskElement;
  }
  render() {
    this.container.innerHTML = `
            <div class="card">
                <h2>\uD83D\uDCE5 媒體下載器</h2>
                <div class="grid-2-col">
                    <!-- 左側：輸入與主要控制 -->
                    <div class="flex-col">
                        <div>
                            <label for="downloader-urls-input"><strong>網址或播放清單</strong> (可輸入多個，每行一個)</label>
                            <textarea id="downloader-urls-input" rows="5" placeholder="支援 YouTube, Facebook, Bilibili 等多數影音網站..." style="width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #ccc; box-sizing: border-box; font-family: inherit;"></textarea>
                        </div>
                        <div style="text-align: center; margin-top: 16px;">
                            <button id="start-download-btn" style="width: 100%; padding: 12px; font-size: 1.1em;">開始下載</button>
                        </div>
                    </div>
                    <!-- 右側：詳細選項 -->
                    <div class="flex-col">
                        <div>
                            <label><strong>下載類型</strong></label>
                            <div style="display: flex; gap: 20px; margin-top: 8px;">
                                <label><input type="radio" name="download-type" value="audio" checked> 純音訊</label>
                                <label><input type="radio" name="download-type" value="video"> 影片</label>
                            </div>
                        </div>

                        <!-- 音訊選項 -->
                        <div id="audio-options">
                            <label for="audio-format-select"><strong>音訊格式</strong></label>
                            <select id="audio-format-select">
                                <option value="m4a">M4A (原生格式, 速度最快)</option>
                                <option value="mp3">MP3 (需轉檔, 相容性高)</option>
                                <option value="wav">WAV (需轉檔, 無損)</option>
                                <option value="flac">FLAC (需轉檔, 無損壓縮)</option>
                            </select>
                        </div>

                        <!-- 影片選項 (預設隱藏) -->
                        <div id="video-options" class="hidden">
                            <label for="video-quality-select"><strong>影片畫質</strong></label>
                            <select id="video-quality-select">
                                <option value="best">最佳畫質</option>
                                <option value="1080p">1080p</option>
                                <option value="720p">720p (HD)</option>
                                <option value="480p">480p (SD)</option>
                            </select>
                        </div>

                        <div>
                            <label><strong>進階功能</strong></label>
                            <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px;">
                                <label><input type="checkbox" id="remove-silence-checkbox"> 移除音訊靜默部分 (僅音訊)</label>
                            </div>
                        </div>

                        <div style="margin-top: 16px;">
                            <label><strong>YouTube 驗證</strong></label>
                             <p style="font-size: 0.85em; color: #666; margin-top: 4px; margin-bottom: 8px;">若下載需要登入的影片失敗，請上傳您的 cookies.txt 檔案。</p>
                            <button id="upload-cookies-btn" style="background-color: #ffc107; color: var(--text-color);">\uD83C\uDF6A 上傳 cookies.txt</button>
                            <input type="file" id="cookies-input" accept=".txt" class="hidden">
                        </div>
                    </div>
                </div>
            </div>

            <!-- 下載列表 -->
            <div class="card" style="margin-top: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
                    <h2>\uD83D\uDCCB 下載佇列與歷史紀錄</h2>
                    <button id="zip-download-btn" disabled style="background-color: #28a745;">打包下載選定項目 (.zip)</button>
                </div>
                <div id="downloader-tasks" class="task-list" style="margin-top: 16px;">
                    <p id="no-downloader-task-msg">暫無下載任務</p>
                </div>
            </div>
        `;
  }
  addEventListeners() {
    const startDownloadBtn = this.container.querySelector("#start-download-btn");
    const downloadTypeRadios = this.container.querySelectorAll('input[name="download-type"]');
    const audioOptions = this.container.querySelector("#audio-options");
    const videoOptions = this.container.querySelector("#video-options");
    const removeSilenceCheckbox = this.container.querySelector("#remove-silence-checkbox");
    const uploadCookiesBtn = this.container.querySelector("#upload-cookies-btn");
    const cookiesInput = this.container.querySelector("#cookies-input");
    const zipDownloadBtn = this.container.querySelector("#zip-download-btn");
    startDownloadBtn.addEventListener("click", () => this.processDownloaderRequest());
    downloadTypeRadios.forEach((radio) => {
      radio.addEventListener("change", (e) => {
        this.logAction("change-download-type", e.target.value);
        if (radio.value === "audio") {
          audioOptions.classList.remove("hidden");
          videoOptions.classList.add("hidden");
          removeSilenceCheckbox.disabled = false;
        } else {
          audioOptions.classList.add("hidden");
          videoOptions.classList.remove("hidden");
          removeSilenceCheckbox.disabled = true;
          removeSilenceCheckbox.checked = false;
        }
      });
    });
    uploadCookiesBtn.addEventListener("click", () => {
      this.logAction("click-upload-cookies-btn");
      cookiesInput.click();
    });
    cookiesInput.addEventListener("change", (event) => this.handleCookiesUpload(event));
    zipDownloadBtn.addEventListener("click", (e) => {
      this.logAction("click-zip-download");
      const downloaderTasksContainer = this.container.querySelector("#downloader-tasks");
      const checkedBoxes = downloaderTasksContainer.querySelectorAll(".task-checkbox:checked");
      if (checkedBoxes.length === 0) {
        this.showStatusMessage("請至少選擇一個要打包下載的項目。", true);
        return;
      }
      const taskIds = Array.from(checkedBoxes).map((cb) => cb.value);
      const url = `/api/zip_download?task_ids=${taskIds.join(",")}`;
      window.location.href = url;
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = "正在打包...";
      setTimeout(() => {
        btn.disabled = false;
        btn.textContent = "打包下載選定項目 (.zip)";
      }, 5000);
    });
  }
  async handleCookiesUpload(event) {
    const file = event.target.files[0];
    if (!file)
      return;
    this.logAction("change-cookies-input", file.name);
    const formData = new FormData;
    formData.append("file", file, "cookies.txt");
    this.showStatusMessage("正在上傳 Cookies...", false, 0);
    try {
      const response = await fetch("/api/upload_cookies", {
        method: "POST",
        body: formData
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || "上傳失敗");
      }
      this.showStatusMessage("Cookies 上傳成功！", false, 5000);
    } catch (error) {
      console.error("Cookies 上傳失敗:", error);
      this.showStatusMessage(`錯誤: ${error.message}`, true, 8000);
    } finally {
      event.target.value = "";
    }
  }
  async processDownloaderRequest() {
    this.logAction("click-start-download");
    const downloaderUrlsInput = this.container.querySelector("#downloader-urls-input");
    const startDownloadBtn = this.container.querySelector("#start-download-btn");
    const downloadType = this.container.querySelector('input[name="download-type"]:checked').value;
    const urls = downloaderUrlsInput.value.split(`
`).map((u) => u.trim()).filter((u) => u);
    if (urls.length === 0) {
      this.showStatusMessage("請輸入至少一個網址。", true);
      return;
    }
    const requests = urls.map((url) => ({ url, filename: "" }));
    const payload = {
      requests,
      download_only: true,
      model: null,
      download_type: downloadType
    };
    startDownloadBtn.disabled = true;
    startDownloadBtn.textContent = "正在建立任務...";
    try {
      const response = await fetch("/api/youtube/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error((await response.json()).detail || "建立下載任務失敗");
      }
      const result = await response.json();
      result.tasks.forEach((task) => {
        const taskType = `僅下載${downloadType === "video" ? "影片" : "音訊"}`;
        const downloaderTaskContainer = this.container.querySelector("#downloader-tasks");
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          this.socket.send(JSON.stringify({ type: "START_YOUTUBE_PROCESSING", payload: { task_id: task.task_id } }));
        }
      });
      downloaderUrlsInput.value = "";
    } catch (error) {
      this.showStatusMessage(`處理下載任務時發生錯誤: ${error.message}`, true);
    } finally {
      startDownloadBtn.disabled = false;
      startDownloadBtn.textContent = "開始下載";
    }
  }
  init() {
    this.render();
    this.addEventListeners();
  }
}

// src/frontend/main.js
class App {
  constructor() {
    this.localTranscriberContainer = document.getElementById("local-file-tab");
    this.mediaDownloaderContainer = document.getElementById("downloader-tab");
    this.tasklistContainer = document.getElementById("task-list-container");
    this.fileBrowserContainer = document.getElementById("file-browser-container");
    this.statusMessageArea = document.getElementById("status-message-area");
    this.statusMessageText = document.getElementById("status-message-text");
    this.modelDisplay = document.getElementById("model-display");
    this.socket = null;
  }
  setupWebSocket() {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${window.location.host}/api/ws`;
    this.socket = new WebSocket(wsUrl);
    this.socket.onopen = () => {
      console.log("WebSocket 連線成功");
      this.logAction("websocket-connect-success");
    };
    this.socket.onmessage = (event) => this.handleWebSocketMessage(JSON.parse(event.data));
    this.socket.onclose = () => {
      console.log("WebSocket 連線已關閉，正在嘗試重新連線...");
      this.logAction("websocket-connect-close");
      setTimeout(() => this.setupWebSocket(), 3000);
    };
    this.socket.onerror = (error) => {
      console.error("WebSocket 發生錯誤:", error);
      this.logAction("websocket-connect-error");
    };
  }
  handleWebSocketMessage(message) {
    console.log("[WebSocket Received]:", message);
    const { type, payload } = message;
    if (type === "DOWNLOAD_STATUS") {
      if (this.localTranscriber) {
        this.localTranscriber.handleModelDownloadStatus(payload);
      }
    } else if (["TRANSCRIPTION_STATUS", "TRANSCRIPTION_UPDATE", "YOUTUBE_STATUS"].includes(type)) {
      if (this.taskList) {
        this.taskList.handleTaskUpdate(payload);
      }
    } else {
      console.warn(`未知的 WebSocket 訊息類型: ${type}`);
    }
  }
  showStatusMessage(message, isError = false, duration = 5000) {
    if (!this.statusMessageArea || !this.statusMessageText)
      return;
    this.statusMessageText.textContent = message;
    this.statusMessageArea.style.display = "block";
    this.statusMessageArea.style.backgroundColor = isError ? "#f8d7da" : "#d4edda";
    this.statusMessageArea.style.borderColor = isError ? "#f5c6cb" : "#c3e6cb";
    this.statusMessageText.style.color = isError ? "#721c24" : "#155724";
    if (duration > 0) {
      setTimeout(() => {
        if (this.statusMessageText.textContent === message) {
          this.statusMessageArea.style.display = "none";
        }
      }, duration);
    }
  }
  logAction(action, value = null) {
    const message = value !== null ? `${action}: ${value}` : action;
    console.log(`Logging action: ${message}`);
    fetch("/api/log/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: message })
    }).catch((err) => console.error("logAction failed:", err));
  }
  setupTabSwitching() {
    const tabContainer = document.querySelector(".tab-container");
    const tabContentContainer = document.getElementById("tab-content-container");
    if (!tabContainer || !tabContentContainer)
      return;
    tabContainer.addEventListener("click", (e) => {
      if (e.target.matches(".tab-button")) {
        const tabId = e.target.dataset.tab;
        this.logAction("click-tab", tabId);
        tabContainer.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));
        e.target.classList.add("active");
        tabContentContainer.querySelectorAll(".tab-content").forEach((content) => {
          if (content.id === tabId) {
            content.classList.add("active");
          } else {
            content.classList.remove("active");
          }
        });
      }
    });
  }
  initComponents() {
    const services = {
      socket: this.socket,
      showStatusMessage: this.showStatusMessage.bind(this),
      logAction: this.logAction.bind(this),
      updateModelDisplay: (modelName) => {
        if (this.modelDisplay)
          this.modelDisplay.textContent = modelName;
      },
      app: this
    };
    if (this.localTranscriberContainer) {
      this.localTranscriber = new LocalTranscriber(this.localTranscriberContainer, services);
      this.localTranscriber.init();
    }
    if (this.mediaDownloaderContainer) {
      this.mediaDownloader = new MediaDownloader(this.mediaDownloaderContainer, services);
      this.mediaDownloader.init();
    }
    if (this.tasklistContainer) {
      const taskListServices = {
        ...services,
        openPreviewModal: (url, name, type, id) => alert(`預覽功能待實現: ${name}`)
      };
      this.taskList = new TaskList(this.tasklistContainer, taskListServices);
      this.taskList.init();
    }
    if (this.fileBrowserContainer) {
      this.fileBrowser = new FileBrowser(this.fileBrowserContainer, services);
      this.fileBrowser.init();
    }
  }
  init() {
    console.log("DOM 已載入，開始初始化應用程式。");
    this.setupWebSocket();
    this.initComponents();
    this.setupTabSwitching();
  }
}
document.addEventListener("DOMContentLoaded", () => {
  const app = new App;
  app.init();
});
