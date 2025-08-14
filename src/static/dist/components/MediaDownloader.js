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
export {
  MediaDownloader
};
