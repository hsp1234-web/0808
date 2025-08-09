# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

[![zh-Hant](https://img.shields.io/badge/language-繁體中文-blue.svg)](README.md)

這是一個高效、可擴展的音訊轉錄專案，旨在提供一個可以透過 Web 介面輕鬆操作的語音轉文字服務。專案目前正處於積極的重構階段，以建立一個更現代化、更穩健的後端架構。

---

## 🚀 核心架構

我們採用了業界成熟的 **「Web 前端 + 異步任務佇列後端」** 架構，以實現最佳的使用者體驗和系統穩定性。

*   **Web 伺服器 (`app/main.py`)**:
    *   基於 **FastAPI** 框架，提供一個輕量級、高效能的 API 服務。
    *   **職責**：
        1.  提供靜態的前端操作介面 (`mp3.html`)。
        2.  接收使用者上傳的音訊檔案，並將「轉錄任務」推入任務佇列。
        3.  立刻對使用者請求做出回應，避免前端頁面卡頓。

*   **背景工作者 (`app/worker.py`)**:
    *   一個獨立的處理程序，與 Web 伺服器並行運作。
    *   **職責**：
        1.  持續監聽任務佇列。
        2.  從佇列中依序取出任務。
        3.  呼叫核心轉錄工具 (`app/core/transcriber.py`) 來執行耗時的語音轉錄工作。
        4.  (未來) 將轉錄結果更新到資料庫或通知前端。

*   **前端介面 (`app/static/mp3.html`)**:
    *   一個純粹的 HTML/CSS/JavaScript 單頁應用。
    *   **職責**：
        1.  提供檔案上傳介面。
        2.  與後端 API 進行非同步通訊。
        3.  動態顯示轉錄狀態與最終結果。

這個架構確保了 Web 服務的快速響應和背景任務的穩定執行，兩者互不干擾，是現代 Web 應用的最佳實踐之一。

---

## 📁 檔案結構

專案採用了功能導向的扁平化結構，將主要服務和模組放置於根目錄。

```
/
|
|-- api_server.py        # Web 伺服器 (FastAPI)，提供 API 和前端介面
|-- worker.py            # 背景工作者，處理耗時的轉錄任務
|-- orchestrator.py      # 系統協調器，負責啟動和監控服務
|
|-- static/              # 前端資源
|   `-- mp3.html         # 主要的單頁應用程式介面
|
|-- db/                  # 資料庫模組
|   |-- database.py      # 資料庫連線和任務佇列邏輯
|   `-- log_handler.py   # 資料庫日誌處理器
|
|-- tools/               # 核心工具與商業邏輯
|   |-- transcriber.py   # 核心轉錄引擎 (Whisper)
|   `-- mock_transcriber.py # 用於測試的模擬轉錄器
|
|-- tests/               # 測試碼
|   |-- e2e.spec.js      # Playwright 端對端測試
|   `-- test_worker.py   # Worker 單元測試
|
|-- verify_frontend.py   # 獨立的前端自動化驗證腳本
|-- requirements.txt     # Python 依賴列表
`-- README.md            # 就是這個檔案
```

---

## 🧪 端對端測試 (E2E Testing)

為了確保前端介面的穩定性與核心功能的正確性，我們引入了 **Playwright** 作為端對端測試框架。這些測試會模擬真實使用者的操作，在瀏覽器中自動執行上傳、狀態檢查等流程。

### 如何執行測試

1.  **安裝依賴套件**:
    確保您已安裝所有 Node.js 和 Python 的依賴。
    ```bash
    npm install
    pip install -r requirements.txt
    pip install -r requirements-worker.txt
    ```

2.  **安裝 Playwright 瀏覽器**:
    首次執行時，需要下載 Playwright 所需的瀏覽器核心。
    ```bash
    npx playwright install --with-deps
    ```

3.  **執行測試**:
    此命令將會啟動後端伺服器（使用模擬模式），並在無頭瀏覽器中執行所有測試案例。
    ```bash
    npx playwright test
    ```

測試腳本位於 `tests/e2e.spec.js`。

### 快速驗證腳本 (Python)

除了上述基於 Node.js 的標準測試流程外，專案還提供了一個更為便捷的 Python 驗證腳本 `verify_frontend.py`。

**用途**：
這個腳本是一個完全獨立的端對端測試器。它會自動處理以下所有事務：
1.  **啟動後端伺服器**：使用 `uvicorn` 啟動一個臨時的 API 伺服器。
2.  **執行瀏覽器操作**：使用 Playwright 模擬使用者與 `mp3.html` 頁面的互動。
3.  **功能驗證**：檢查日誌以確認按鈕點擊、檔案上傳等功能是否如預期般運作。
4.  **產生結果**：成功時會產生一張 `frontend_verification.png` 螢幕截圖。
5.  **自動清理**：測試結束後會自動關閉伺服器並刪除臨時檔案。

**如何執行**：
只需一行指令即可完成所有驗證：
```bash
python verify_frontend.py
```
這個腳本是進行快速、完整的前端功能回歸測試的理想選擇。

---

## 📈 目前進度

**專案重構第一階段：架構與檔案結構重建 - ✅ 已完成**

*   [x] 與專案關係人達成共識，確立了全新的 **「Web 前端 + 異步任務佇列後端」** 架構。
*   [x] 重新規劃了專案的檔案與目錄結構，使其更清晰、更專業。
*   [x] 刪除了舊的、不再使用的程式碼與設定檔。
*   [x] 建立了新架構所需的所有檔案與目錄的佔位符。
*   [x] 更新了 `requirements.txt` 以反映新架構的技術選型。
*   [x] 撰寫了此 `README.md` 文件，記錄了新的架構和進度。

## ⏭️ 下一步

接下來，我們將進入程式碼實現階段：

1.  **實現後端 API 伺服器**：在 `app/main.py` 中編寫 FastAPI 程式碼，提供網頁和 API 端點。
2.  **整合語音轉錄功能**：在 `app/core/transcriber.py` 中實現轉錄邏輯。
3.  **開發前端互動功能**：更新 `app/static/mp3.html` 中的 JavaScript，使其能與後端通訊。
4.  **實現背景工作者**：在 `app/worker.py` 中編寫從佇列讀取並執行任務的邏輯。
5.  **改造 Colab 啟動器**：微調 `colab.py` 以適應並啟動新架構。
