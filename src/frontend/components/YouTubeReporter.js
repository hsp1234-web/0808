// src/frontend/components/YouTubeReporter.js
import { TaskList } from './TaskList.js';

/**
 * YouTube 轉報告功能組件
 *
 * 負責管理以下功能：
 * 1. Google API 金鑰的輸入、儲存與驗證。
 * 2. YouTube 影片連結的輸入與管理 (新增/刪除列)。
 * 3. AI 分析任務的參數設定 (模型、任務類型、輸出格式)。
 * 4. 觸發「僅下載音訊」或「分析影片」的後端 API 請求。
 * 5. 顯示已完成的 YouTube 報告列表。
 */
export class YouTubeReporter {
    constructor(container, deps) {
        this.container = container;
        this.api = deps.api;
        this.showStatusMessage = deps.showStatusMessage;
        this.openPreviewModal = deps.openPreviewModal;
        this.logAction = deps.logAction;
        this.taskManager = deps.taskManager;

        // 用於存放已完成報告的列表
        this.completedReports = [];
    }

    init() {
        this.render();
        this.addEventListeners();
        this.initializeYouTubeTab();
    }

    render() {
        this.container.innerHTML = `
            <div id="youtube-report-tab" class="tab-content active flex flex-col gap-6">
                <div class="card">
                    <!-- 區域 1: API 金鑰管理 -->
                    <div class="flex justify-between items-center flex-wrap gap-4">
                        <h2>🔑 Google API 金鑰管理</h2>
                        <a href="/static/prompts.html" target="_blank" class="font-semibold text-btn-bg hover:underline">管理提示詞 &rarr;</a>
                    </div>
                    <div class="flex gap-2.5 items-center flex-wrap mt-3">
                        <input type="password" id="api-key-input" placeholder="在此貼上您的 Google API 金鑰" class="flex-grow">
                        <button id="save-api-key-btn" class="btn btn-primary">儲存金鑰</button>
                        <button id="clear-api-key-btn" class="btn bg-gray-500 text-white hover:bg-gray-600">清除金鑰</button>
                    </div>
                    <p id="api-key-status" class="mt-3 font-semibold">狀態: <span class="italic">尚未提供金鑰</span></p>

                    <!-- 區域 2: YouTube 影片處理 -->
                    <h2 class="mt-6">▶️ 輸入 YouTube 影片</h2>
                    <fieldset id="youtube-controls-fieldset" class="mt-3">
                        <div id="youtube-link-list" class="flex flex-col gap-2.5">
                            <div class="youtube-link-row flex flex-wrap gap-2.5 items-center">
                                <input type="text" class="youtube-url-input flex-grow min-w-[300px]" placeholder="YouTube 影片網址">
                                <input type="text" class="youtube-filename-input flex-grow min-w-[150px]" placeholder="自訂檔名 (可選)">
                                <button class="remove-youtube-row-btn btn bg-red-600 text-white hover:bg-red-700 px-4 text-2xl leading-none flex-shrink-0">×</button>
                            </div>
                        </div>
                        <button id="add-youtube-row-btn" class="btn btn-primary mt-3">+ 新增一列</button>
                    </fieldset>
                </div>

                <!-- 區域 3: 參數控制區 -->
                <div class="card">
                    <h2>⚙️ 參數控制區</h2>
                    <fieldset id="youtube-params-fieldset" disabled class="mt-3">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div class="flex flex-col gap-2">
                                <label class="font-semibold">任務選項</label>
                                <div id="yt-tasks-group" class="flex flex-col gap-2 mt-1">
                                    <label class="flex items-center gap-2"><input type="checkbox" name="yt-task" value="summary" checked> 重點摘要</label>
                                    <label class="flex items-center gap-2"><input type="checkbox" name="yt-task" value="transcript" checked> 詳細逐字稿</label>
                                    <label class="flex items-center gap-2"><input type="checkbox" name="yt-task" value="translate"> 翻譯為英文 (基於逐字稿)</label>
                                </div>
                            </div>
                            <div class="flex flex-col gap-4">
                                <div class="flex flex-col gap-2">
                                    <label for="gemini-model-select" class="font-semibold">AI 模型</label>
                                    <select id="gemini-model-select">
                                        <option>等待從伺服器載入模型列表...</option>
                                    </select>
                                </div>
                                <div class="flex flex-col gap-2">
                                    <label for="yt-output-format-select" class="font-semibold">輸出格式</label>
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
                <div class="flex justify-center gap-4 flex-wrap">
                    <button id="download-audio-only-btn" class="btn btn-primary bg-gray-600 hover:bg-gray-700">🎧 僅下載音訊</button>
                    <button id="start-youtube-processing-btn" class="btn btn-primary text-lg" disabled>🚀 分析影片 (Gemini)</button>
                </div>

                <!-- 區域 5: YouTube 報告瀏覽區 -->
                <div id="youtube-file-browser-container" class="card">
                    <h2>📊 YouTube 報告瀏覽區</h2>
                    <div id="youtube-file-browser" class="task-list mt-4">
                        <p id="no-youtube-report-msg" class="text-gray-500 text-center">尚無已完成的報告</p>
                    </div>
                </div>
            </div>
        `;
        this.cacheDomElements();
    }

    cacheDomElements() {
        this.apiKeyInput = this.container.querySelector('#api-key-input');
        this.saveApiKeyBtn = this.container.querySelector('#save-api-key-btn');
        this.clearApiKeyBtn = this.container.querySelector('#clear-api-key-btn');
        this.apiKeyStatus = this.container.querySelector('#api-key-status');
        this.startYoutubeProcessingBtn = this.container.querySelector('#start-youtube-processing-btn');
        this.downloadAudioOnlyBtn = this.container.querySelector('#download-audio-only-btn');
        this.geminiModelSelect = this.container.querySelector('#gemini-model-select');
        this.addYoutubeRowBtn = this.container.querySelector('#add-youtube-row-btn');
        this.youtubeLinkList = this.container.querySelector('#youtube-link-list');
        this.youtubeParamsFieldset = this.container.querySelector('#youtube-params-fieldset');
        this.ytOutputFormatSelect = this.container.querySelector('#yt-output-format-select');
        this.youtubeFileBrowser = this.container.querySelector('#youtube-file-browser');
        this.noYoutubeReportMsg = this.container.querySelector('#no-youtube-report-msg');
    }

    addEventListeners() {
        this.saveApiKeyBtn.addEventListener('click', () => {
            const apiKey = this.apiKeyInput.value.trim();
            this.logAction('click-save-api-key');
            if (apiKey) {
                localStorage.setItem('googleApiKey', apiKey);
                this.validateApiKey(apiKey);
            } else {
                this.showStatusMessage('API 金鑰不能為空', true);
            }
        });

        this.clearApiKeyBtn.addEventListener('click', () => {
            this.logAction('click-clear-api-key');
            localStorage.removeItem('googleApiKey');
            this.apiKeyInput.value = '';
            this.updateApiKeyUI('not_provided');
            this.geminiModelSelect.innerHTML = '<option>提供有效金鑰後將載入模型</option>';
        });

        this.addYoutubeRowBtn.addEventListener('click', () => this.addNewYoutubeRow());

        this.youtubeLinkList.addEventListener('click', (e) => {
            if (e.target && e.target.classList.contains('remove-youtube-row-btn')) {
                this.logAction('click-remove-youtube-row');
                if (this.youtubeLinkList.querySelectorAll('.youtube-link-row').length > 1) {
                    e.target.closest('.youtube-link-row').remove();
                } else {
                    this.showStatusMessage('至少需要保留一列。', true, 3000);
                }
            }
        });

        this.youtubeLinkList.addEventListener('input', (e) => {
            if (e.target && e.target.classList.contains('youtube-filename-input')) {
                e.target.value = this.sanitizeFilename(e.target.value);
            }
        });

        this.downloadAudioOnlyBtn.addEventListener('click', () => this.processYoutubeRequest(true));
        this.startYoutubeProcessingBtn.addEventListener('click', () => this.processYoutubeRequest(false));
    }

    initializeYouTubeTab() {
        this.logAction('initialize-youtube-tab');
        const storedApiKey = localStorage.getItem('googleApiKey');
        if (storedApiKey) {
            this.apiKeyInput.value = storedApiKey;
            this.validateApiKey(storedApiKey);
        } else {
            this.updateApiKeyUI('not_provided');
            this.geminiModelSelect.innerHTML = '<option>提供有效金鑰後將載入模型</option>';
        }
    }

    updateApiKeyUI(state, message) {
        const statusSpan = this.apiKeyStatus.querySelector('span');
        statusSpan.style.color = 'inherit';
        statusSpan.style.fontStyle = 'normal';

        const isValid = state === 'valid';
        this.startYoutubeProcessingBtn.disabled = !isValid;
        this.youtubeParamsFieldset.disabled = !isValid;

        switch (state) {
            case 'valid':
                statusSpan.textContent = message || '驗證成功';
                statusSpan.style.color = 'var(--status-green)';
                this.startYoutubeProcessingBtn.title = '';
                break;
            case 'invalid':
                statusSpan.textContent = message || '驗證失敗';
                statusSpan.style.color = '#dc3545';
                this.startYoutubeProcessingBtn.title = '請提供有效的 API 金鑰以啟用此功能';
                break;
            case 'validating':
                statusSpan.textContent = message || '正在驗證中...';
                statusSpan.style.fontStyle = 'italic';
                break;
            case 'not_provided':
            default:
                statusSpan.textContent = message || '尚未提供金鑰';
                statusSpan.style.fontStyle = 'italic';
                this.startYoutubeProcessingBtn.title = '請提供有效的 API 金鑰以啟用此功能';
                break;
        }
    }

    async validateApiKey(apiKey) {
        if (!apiKey) {
            this.updateApiKeyUI('not_provided');
            return;
        }
        this.updateApiKeyUI('validating');
        try {
            // JULES: 為了讓金鑰在後端生效以載入模型列表，我們不再分離驗證和載入
            // 我們直接嘗試載入模型，如果成功，就代表金鑰有效。
            await this.loadGeminiModels(apiKey);
            this.updateApiKeyUI('valid', '金鑰有效，Gemini 功能已啟用');
        } catch (error) {
            console.error('API Key validation/loading error:', error);
            const errorMessage = error.detail || '金鑰無效或無法載入模型列表';
            this.updateApiKeyUI('invalid', errorMessage);
            this.geminiModelSelect.innerHTML = `<option>${errorMessage}</option>`;
        }
    }

    async loadGeminiModels(apiKey) {
        // JULES: 讓此函式能接收一個臨時金鑰，用於驗證流程
        // 這樣就不需要依賴後端設定的全域金鑰
        try {
            const modelsData = await this.api.youtube.getModels(apiKey);
            this.geminiModelSelect.innerHTML = '';
            if (modelsData && modelsData.models && modelsData.models.length > 0) {
                modelsData.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = model.name;
                    this.geminiModelSelect.appendChild(option);
                });
                this.logAction('load-gemini-models-success');
            } else {
                throw new Error("模型列表為空或格式不符。");
            }
        } catch (error) {
            console.error("載入 Gemini 模型時出錯:", error);
            this.logAction('load-gemini-models-failed', error.detail || error.message);
            // 將錯誤向上拋出，讓 validateApiKey 能夠捕獲
            throw error;
        }
    }

    addNewYoutubeRow() {
        this.logAction('click-add-youtube-row');
        const firstRow = this.youtubeLinkList.querySelector('.youtube-link-row');
        if (!firstRow) return;
        const newRow = firstRow.cloneNode(true);
        newRow.querySelector('.youtube-url-input').value = '';
        newRow.querySelector('.youtube-filename-input').value = '';
        this.youtubeLinkList.appendChild(newRow);
    }

    sanitizeFilename(filename) {
        return filename.replace(/[\\/?%*:|"<>\x00-\x1F]/g, '');
    }

    async processYoutubeRequest(downloadOnly = false) {
        const action = downloadOnly ? 'click-download-audio-only' : 'click-start-youtube-processing';
        this.logAction(action);

        const rows = this.youtubeLinkList.querySelectorAll('.youtube-link-row');
        const requests = Array.from(rows).map(row => {
            const urlInput = row.querySelector('.youtube-url-input');
            const filenameInput = row.querySelector('.youtube-filename-input');
            return {
                url: urlInput.value.trim(),
                filename: filenameInput.value.trim()
            };
        }).filter(req => req.url);

        if (requests.length === 0) {
            this.showStatusMessage('請輸入至少一個有效的 YouTube 網址。', true);
            return;
        }

        const selectedTasks = Array.from(this.container.querySelectorAll('input[name="yt-task"]:checked')).map(cb => cb.value);
        if (!downloadOnly && selectedTasks.length === 0) {
            this.showStatusMessage('請至少選擇一個 AI 分析任務。', true);
            return;
        }

        const button = downloadOnly ? this.downloadAudioOnlyBtn : this.startYoutubeProcessingBtn;
        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = '正在建立任務...';

        try {
            const payload = {
                requests: requests,
                model: this.geminiModelSelect.value,
                download_only: downloadOnly,
                tasks: selectedTasks.join(','),
                output_format: this.ytOutputFormatSelect.value,
                api_key: localStorage.getItem('googleApiKey') // JULES: 將儲存的金鑰加入請求
            };

            const result = await this.api.youtube.process(payload);

            result.tasks.forEach(task => {
                this.taskManager.startTask(task);
            });

            // 清空輸入框
            const allRows = this.youtubeLinkList.querySelectorAll('.youtube-link-row');
            allRows.forEach((row, index) => {
                if (index === 0) {
                    row.querySelector('.youtube-url-input').value = '';
                    row.querySelector('.youtube-filename-input').value = '';
                } else {
                    row.remove();
                }
            });

        } catch (error) {
            // JULES: 顯示來自後端的詳細錯誤訊息
            this.showStatusMessage(`處理 YouTube 任務時發生錯誤: ${error.detail || error.message}`, true);
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    addYoutubeReportToList(payload) {
        // This method will be called by the TaskManager when a youtube report task is completed
        if (this.noYoutubeReportMsg && this.noYoutubeReportMsg.style.display !== 'none') {
            this.noYoutubeReportMsg.style.display = 'none';
        }

        const result = payload.result || {};
        const taskId = payload.task_id;
        const videoTitle = result.video_title || '無標題報告';
        const outputPath = result.output_path || '';
        // ... (rest of the logic to create and append the report element)
    }
}
