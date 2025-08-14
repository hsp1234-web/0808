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
export {
  LocalTranscriber
};
