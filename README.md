# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

[![zh-Hant](https://img.shields.io/badge/language-繁體中文-blue.svg)](README.md)

這是一個高效、可擴展的音訊轉錄專案，旨在提供一個可以透過 Web 介面輕鬆操作的語音轉文字服務。專案近期已整合 **YouTube 影片處理與 AI 分析** 功能。

---

## 🚀 核心架構

我們採用了業界成熟的 **「Web 前端 + 異步任務後端」** 架構，以實現最佳的使用者體驗和系統穩定性。

*   **Web 伺服器 (`api_server.py`)**:
    *   基於 **FastAPI** 框架，提供一個輕量級、高效能的 API 服務。
    *   **職責**：
        1.  提供靜態的前端操作介面 (`static/mp3.html`)。
        2.  接收使用者上傳的檔案或 YouTube 網址，並將任務推入資料庫佇列。
        3.  透過 **WebSocket** 與前端進行即時雙向通訊，回報任務進度。
        4.  在背景執行緒中，呼叫對應的工具 (`tools/`) 來處理任務。

*   **資料庫模組 (`db/`)**:
    *   使用 **SQLite** 作為輕量級的資料庫，實現了一個可靠的任務佇列。
    *   `db/manager.py` 作為一個獨立的伺服器程序，統一管理所有資料庫操作，避免多程序寫入衝突。
    *   `db/client.py` 提供一個簡單的客戶端，讓其他程序可以安全地與 `manager` 通訊。

*   **前端介面 (`static/mp3.html`)**:
    *   一個純粹的 HTML/CSS/JavaScript 單頁應用。
    *   **職責**：
        1.  提供「本地檔案轉錄」和「YouTube 影片處理」兩種功能的 UI。
        2.  與後端 API 和 WebSocket 進行非同步通訊。
        3.  動態顯示任務狀態與最終結果。

*   **系統協調器 (`orchestrator.py`)**:
    *   整個應用程式的啟動與監控中心。
    *   負責依序、可靠地啟動資料庫管理者和 API 伺服器。

---

## 📁 檔案結構

專案採用了功能導向的扁平化結構，將主要服務和模組放置於根目錄。

```
/
|
|-- api_server.py        # Web 伺服器 (FastAPI)，提供 API 和前端介面
|-- orchestrator.py      # 系統協調器，負責啟動和監控服務
|
|-- static/              # 前端資源
|   `-- mp3.html         # 主要的單頁應用程式介面
|
|-- db/                  # 資料庫模組
|   |-- database.py      # 核心資料庫操作 (SQLite)
|   |-- manager.py       # 資料庫管理者伺服器
|   `-- client.py        # 資料庫客戶端
|
|-- tools/               # 核心工具與商業邏輯
|   |-- transcriber.py   # 核心轉錄引擎 (Whisper)
|   |-- youtube_downloader.py # YouTube 音訊下載器
|   |-- gemini_processor.py   # Gemini AI 分析與報告生成器
|   `-- mock_*.py        # 用於測試的模擬工具
|
|-- tests/               # 測試碼
|   `-- verify_*.py      # Playwright 端對端驗證腳本
|
|-- requirements.txt     # Python 依賴列表
`-- README.md            # 就是這個檔案
```

---

## ⚡️ 如何啟動應用程式

啟動整個應用程式（包括資料庫和 API 伺服器）的最推薦方式是透過協調器。

1.  **安裝依賴**
    ```bash
    pip install -r requirements.txt
    ```

2.  **啟動應用程式**
    *   **模擬模式 (建議)**：此模式會使用模擬的工具，不會實際呼叫外部 API，適合開發和測試前端。
        ```bash
        python orchestrator.py --mock
        ```
    *   **真實模式**：此模式會呼叫真實的 Whisper 和 Gemini API，請確保已設定好相關的 API 金鑰。
        ```bash
        python orchestrator.py --no-mock
        ```

    成功啟動後，協調器會顯示 API 伺服器正在運行的埠號，例如 `API_PORT: 56753`。請在瀏覽器中開啟 `http://127.0.0.1:56753` 來存取介面。

---

## 📈 目前進度與狀態

**專案重構與 YouTube 功能整合 - ✅ 已完成**

*   [x] **架構重構**：成功將專案重構為目前的多程序架構（協調器、資料庫管理器、API 伺服器）。
*   [x] **YouTube 功能整合**：已完成 `YouTube.md` 中規劃的所有開發階段。
    *   [x] **後端**：`api_server.py` 已具備接收 YouTube 處理請求、建立任務、並透過 WebSocket 回報進度的能力。
    *   [x] **前端**：`static/mp3.html` 已更新，包含一個全新的分頁介面，使用者可以提交 YouTube URL 並查看處理結果。
*   [x] **模擬工具**：建立了 `mock_youtube_downloader.py` 和 `mock_gemini_processor.py`，以利於在沒有 API 金鑰的情況下進行開發與測試。
*   [x] **錯誤修復**：解決了數個在開發過程中發現的、與程序間通訊和狀態同步相關的競爭條件 (Race Condition) 錯誤。

## ⚠️ 已知問題與後續步驟

*   **未完成事項 - 端對端測試**：
    *   儘管為新功能編寫了 Playwright 自動化測試腳本 (`jules-scratch/verification/verify_youtube_feature.py`)，但由於測試環境的持續性不穩定問題（例如，背景程序意外崩潰、埠號衝突），導致測試無法穩定地執行成功。
*   **後續建議**：
    1.  **穩定化測試環境**：在一個更穩定、乾淨的環境中，重新執行 Playwright 測試，以正式驗證功能的完整性。
    2.  **模型列表 API**：目前前端的 Gemini 模型列表是硬編碼的。可以新增一個後端 API 端點來動態提供此列表，以提高未來的可擴展性。
    3.  **頁內預覽**：目前生成的 HTML 報告是在新分頁中開啟的。可以按照原計畫，將其改為在頁面內直接預覽，以提升使用者體驗。
