## 906號 - 2025-09-01T07:10:00+08:00

### fix(core): 修正 Gemini API 呼叫與 E2E 測試環境

- **動機**: 解決 `gemini_processor.py` 中因 API 參數錯誤導致的 `TypeError`，並修復一系列連鎖的 E2E 測試環境問題，以恢復系統穩定性。
- **核心變更**:
    - **修正 API 呼叫 (`gemini_processor.py`)**: 移除了 `genai.upload_file` 函式中不被支援的 `request_options` 參數，解決了檔案上傳失敗的根本原因。
    - **加固測試伺服器啟動器 (`scripts/run_server_for_playwright.py`)**:
        - 新增了安裝 `psmisc` 套件的邏輯，以確保 `fuser` 指令可用。
        - 在伺服器啟動前，使用 `fuser` 強制清理被佔用的埠號，解決了 `Address already in use` 錯誤。
        - 為子程序正確設定了 `PYTHONPATH`，解決了 `ModuleNotFoundError`。
    - **修復後端 API (`api_server.py`)**: 完整實作了前端所需的 `/api/app_state` 端點，解決了導致 UI 渲染失敗的 404 錯誤。
- **已知問題**: 儘管所有已知的後端和環境錯誤都已修復，E2E 測試依然超時。問題可能位於前端渲染邏輯，已在 `HANDOVER_PLAN.md` 中留下詳細的除錯建議。

## 901號 - 2025-09-01T00:10:00+08:00

### feat(launcher): 實作智慧依賴檢查以加速啟動

- **動機**: 解決 `colabPro.py` 啟動器每次都重新安裝所有 Python 依賴，導致啟動時間過長的問題。
- **核心變更**:
    - **新增依賴檢查腳本 (`scripts/check_deps.py`)**: 建立了一個新的輕量級腳本，它能透過 `importlib` 檢查指定的套件是否已在環境中安裝，並回報真正缺失的套件列表。
    - **改造 `colabPro.py` 安裝流程**:
        - 在安裝依賴前，會先呼叫 `check_deps.py` 進行檢查。
        - 如果沒有任何套件缺失，則完全跳過安裝步驟，並印出提示訊息，大幅縮短了啟動時間。
        - 如果有套件缺失，則只針對缺失的套件進行安裝，避免了不必要的重複工作。
    - **配置更新**:
        - 將預設後端版本 (`TARGET_BRANCH_OR_TAG`) 更新為使用者指定的 `902`。
        - 將預設日誌顯示行數 (`LOG_DISPLAY_LINES`) 調整為 `10`。
- **成果**: 此項優化顯著提升了重複啟動時的使用者體驗，使得啟動器更加智慧和高效。

## 898號 - 2025-08-31T16:10:00+08:00

### refactor(core): 實現真正的無狀態 API 金鑰處理架構

- **動機**: 舊的架構在後端透過環境變數 (`os.environ`) 保存了 API 金鑰的狀態。這種設計不僅複雜，且在獨立的 HTTP 請求之間狀態容易遺失，是導致「模型列表載入失敗」等問題的根本原因。
- **核心變更**:
    - **前端 (`src/static/mp3.html`)**:
        - 修改了 `processYoutubeRequest` 函式，確保在發起「分析影片」請求時，會從 `localStorage` 讀取 API 金鑰，並將其包含在請求的酬載 (payload) 中。
    - **後端 (`src/api/api_server.py`)**:
        - **實現無狀態化**:
            - 從 `validate_api_key` 函式中徹底移除了 `os.environ["GOOGLE_API_KEY"] = api_key` 這一行，使後端不再於請求之間保存任何金鑰狀態。
            - 修改了 `process_youtube_urls` 端點，使其能從請求酬載中直接接收 `api_key`。
            - 修改了任務建立邏輯，將接收到的 `api_key` 存入 `gemini_process` 任務的資料庫酬載中。
        - **實現單次使用**:
            - 修改了 `trigger_youtube_processing` 函式。在執行 `gemini_processor.py` 子程序時，會從任務酬載中讀取金鑰，並**僅為該次子程序呼叫**將其設定到環境變數中。
- **成果**: 此次重構徹底簡化了金鑰管理模型。後端現在是完全無狀態的，每一次需要金鑰的操作都由前端明確提供，從根本上解決了因狀態遺失導致的各類錯誤，大幅提升了系統的健壯性與可預測性。
