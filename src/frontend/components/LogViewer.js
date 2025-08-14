/**
 * LogViewer 組件
 *
 * 負責渲染和管理系統日誌查看器，包括篩選和從後端獲取日誌。
 */
export class LogViewer {
    constructor(container, deps) {
        this.container = container;
        this.showStatusMessage = deps.showStatusMessage;
        this.logAction = deps.logAction;
    }

    init() {
        this.render();
        this.addEventListeners();
    }

    render() {
        // This HTML is from damo.html
        this.container.innerHTML = `
            <div id="log-viewer-card" class="card">
                <h2>📜 系統日誌查看器</h2>
                <div class="log-controls">
                    <strong>等級:</strong>
                    <label><input type="checkbox" name="log-level" value="INFO" checked> INFO</label>
                    <label><input type="checkbox" name="log-level" value="SUCCESS" checked> SUCCESS</label>
                    <label><input type="checkbox" name="log-level" value="WARN" checked> WARN</label>
                    <label><input type="checkbox" name="log-level" value="ERROR" checked> ERROR</label>
                    <label><input type="checkbox" name="log-level" value="CRITICAL" checked> CRITICAL</label>
                </div>
                <div class="log-controls" style="margin-top: 10px;">
                    <strong>來源:</strong>
                    <label><input type="checkbox" name="log-source" value="colab_setup" checked> Setup</label>
                    <label><input type="checkbox" name="log-source" value="orchestrator" checked> Orchestrator</label>
                    <label><input type="checkbox" name="log-source" value="api_server" checked> API Server</label>
                    <label><input type="checkbox" name="log-source" value="worker" checked> Worker</label>
                </div>
                <div style="margin-top: 16px; display: flex; gap: 10px;">
                    <button id="fetch-logs-btn">🔄 更新日誌</button>
                    <button id="copy-logs-btn">📋 複製日誌</button>
                </div>
                <pre id="log-output" class="transcript-output" style="margin-top: 16px; min-height: 200px; max-height: 500px; overflow-y: auto;">點擊「更新日誌」以載入...</pre>
            </div>
        `;
    }

    addEventListeners() {
        const fetchLogsBtn = this.container.querySelector('#fetch-logs-btn');
        const copyLogsBtn = this.container.querySelector('#copy-logs-btn');
        const logOutput = this.container.querySelector('#log-output');

        fetchLogsBtn.addEventListener('click', async () => {
            this.logAction('click-fetch-logs');
            logOutput.textContent = '載入中...';
            try {
                const levels = Array.from(this.container.querySelectorAll('input[name="log-level"]:checked')).map(el => el.value);
                const sources = Array.from(this.container.querySelectorAll('input[name="log-source"]:checked')).map(el => el.value);
                const params = new URLSearchParams();
                levels.forEach(level => params.append('level', level));
                sources.forEach(source => params.append('source', source));

                const response = await fetch(`/api/logs?${params.toString()}`);
                if (!response.ok) throw new Error(`伺服器錯誤: ${response.statusText}`);

                const logs = await response.json();
                if (logs.length === 0) {
                    logOutput.textContent = '找不到符合條件的日誌。';
                } else {
                    logOutput.textContent = logs.map(log => `[${new Date(log.timestamp).toLocaleString()}] [${log.source}] [${log.level}] ${log.message}`).join('\\n');
                }
            } catch (error) {
                logOutput.textContent = `載入日誌時發生錯誤: ${error.message}`;
            }
        });

        copyLogsBtn.addEventListener('click', () => {
            this.logAction('click-copy-logs');
            navigator.clipboard.writeText(logOutput.textContent)
                .then(() => this.showStatusMessage('日誌已複製到剪貼簿！', false, 3000))
                .catch(err => this.showStatusMessage('複製失敗: ' + err, true));
        });
    }
}
