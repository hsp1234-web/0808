# 工具與測試方法說明 (tool.md)

本文件旨在詳細說明此專案中使用的工具、檔案結構、測試方法以及近期的主要修改。

## 1. 專案核心工具與檔案功能

本專案採用多程序架構，由一個主協調器啟動並管理各個服務。

| 檔案/工具 | 位置 | 功能說明 |
| :--- | :--- | :--- |
| **`orchestrator.py`** | `.` | **系統大腦/協調器**。這是執行本地服務的主入口點。它負責啟動 `db_manager.py` 和 `api_server.py`，並監控它們的狀態。 |
| **`db_manager.py`** | `db/` | **資料庫管理服務**。一個獨立的 TCP 伺服器，作為資料庫的唯一寫入點，處理來自其他服務的請求，避免多程序同時寫入 SQLite 造成的鎖定問題。 |
| **`db/client.py`** | `db/` | **資料庫客戶端**。提供一個簡單的介面，讓其他服務 (如 `api_server`) 可以像呼叫函式一樣，透過網路向 `db_manager` 發送指令。 |
| **`db/database.py`** | `db/` | **資料庫操作模組**。定義了資料庫綱要 (schema) 和所有直接與 SQLite 資料庫 (`queue.db`) 互動的 SQL 操作函式。 |
| **`api_server.py`** | `.` | **核心後端 API 伺服器**。基於 FastAPI 框架，負責處理所有 HTTP 請求，提供 RESTful API，並透過 WebSocket 與前端進行即時通訊。 |
| **`static/mp3.html`** | `static/` | **主要前端介面**。一個單頁應用程式 (SPA)，包含了使用者操作所需的所有 HTML、CSS 和 JavaScript。 |
| **`colab.py`** | `.` | **Google Colab 前端入口**。這是一個獨立的 Jupyter Notebook 腳本，用於在 Google Colab 環境中一鍵部署和啟動整個應用。它會自動處理 Git 拉取、依賴安裝和啟動 `orchestrator.py`。 |
| **`requirements.txt`** | `.` | 定義了專案運行的所有 Python 依賴套件。 |
| **`tools/`** | `tools/` | 包含一些輔助工具腳本，例如真實的轉錄工具 (`transcriber.py`) 和用於測試的模擬工具 (`mock_transcriber.py`)。 |

---

## 2. 近期主要修改與方法

我近期進行了以下幾項關鍵的修改與錯誤修復：

### a. 修復 `colab.py` 日誌截斷問題
*   **問題**: `colab.py` 在任務結束時保存的日誌檔案內容不完整。
*   **原因**: `LogManager` 類別使用了一個有長度上限的 `deque` 來儲存日誌，導致舊日誌被丟棄。
*   **修改方法**: 我在 `LogManager` 中新增了一個沒有長度限制的 `list` (`_full_history`)，與原有的 `deque` 分開。`log` 方法會同時寫入這兩者，而最終存檔時則從 `_full_history` 讀取完整日誌。

### b. 建立全系統日誌記錄機制
*   **目標**: 將所有服務的日誌統一記錄到資料庫中，以便集中查看。
*   **修改方法**:
    1.  在 `db/database.py` 中新增了 `add_system_log` 和 `get_system_logs_by_filter` 兩個函式。
    2.  在 `db/manager.py` 的 `ACTION_MAP` 中註冊了新的 `get_system_logs` 動作。
    3.  在 `db/client.py` 中新增了 `get_system_logs` 客戶端方法。
    4.  在 `api_server.py` 和 `orchestrator.py` 中，重新啟用了原先被註解掉的 `setup_database_logging()`，使其日誌能寫入資料庫。
    5.  在 `colab.py` 中，透過動態載入模組的方式，呼叫 `add_system_log` 來記錄 Git 和 pip 的安裝過程。

### c. 修復網路通訊中的間歇性錯誤
*   **問題**: 日誌查看器偶爾會發生「伺服器錯誤」，日誌顯示 `json.decoder.JSONDecodeError: Unterminated string`。
*   **原因**: `db/client.py` 在透過 socket 接收 `db_manager` 的回應時，假設 `sock.recv(size)` 會一次性收到所有資料。在網路繁忙或資料量大時，這並不是必然的，導致客戶端只收到了不完整的 JSON 字串就進行解析。
*   **修改方法**: 我將 `sock.recv()` 放入一個 `while` 迴圈中，並不斷累加接收到的資料，直到總長度與標頭 (header) 中指定的長度相符為止。這確保了客戶端總是在處理一個完整的 JSON 回應。

### d. 實現新的前端預覽功能
*   **目標**: 將「預覽」按鈕的彈窗行為，改為在頁面下方顯示內容。
*   **修改方法**:
    1.  在 `static/mp3.html` 中新增一個預設隱藏的 `<div>` 作為預覽區 (`id="preview-area"`)。
    2.  修改 JavaScript，讓「預覽」按鈕被點擊時：
        *   使用 `fetch` 呼叫 `/api/download/{task_id}` 來獲取文字內容。
        *   將內容填入預覽區。
        *   移除預覽區的 `hidden` class使其可見。
        *   使用 `scrollIntoView()` 將頁面平滑捲動到預覽區。

---

## 3. 我的測試方法

由於無法直接操作圖形介面，我採用了 **Playwright** 進行端對端 (E2E) 自動化測試，以模擬真實使用者的操作流程。

### a. 環境準備
1.  **啟動服務**: 在終端中以後台模式執行 `python orchestrator.py > orchestrator.log 2>&1 &` 來啟動整個應用程式。
2.  **安裝依賴**: 執行 `pip install -r requirements.txt` 以確保所有測試和執行環境的依賴都已安裝。
3.  **取得埠號**: 透過 `grep "API_PORT" orchestrator.log` 從日誌中獲取 `api_server` 的動態埠號。

### b. 測試腳本編寫
我編寫了一個測試腳本 (`jules-scratch/verification/verify_all_features.py`)，其步驟如下：
1.  **導航**: 使用 Playwright 前往 `api_server` 所在的 URL。
2.  **測試日誌系統**:
    *   點擊「更新日誌」按鈕。
    *   斷言 (Assert) 日誌區塊中**沒有**出現「伺服器錯誤」的訊息，並**有**出現預期的啟動日誌。這驗證了網路通訊的修復是成功的。
3.  **測試檔案上傳與預覽**:
    *   使用 `create_dummy_audio.py` 產生一個測試用的音訊檔。
    *   在測試腳本中，模擬使用者上傳此音訊檔。
    *   輪詢 UI，直到該任務出現在「已完成任務」列表中。
    *   點擊該任務的「預覽」按鈕。
    *   斷言 (Assert) 頁面下方的預覽區塊變為可見，並且其內容與模擬轉錄工具產生的預期文字相符。
4.  **產生螢幕截圖**: 在測試的最後，使用 `page.screenshot()` 產生一個螢幕截圖，用於視覺化驗證。

### c. 偵錯流程
在測試過程中，我遇到了數個問題，以下是我的偵錯方法：
*   **伺服器啟動失敗**: 仔細閱讀 `orchestrator.log`，根據 traceback 找出根本原因（如：`ModuleNotFoundError`、競爭條件等），並修正程式碼。
*   **測試腳本失敗**:
    *   **路徑問題 (`ENOENT`)**: 當上傳檔案失敗時，我嘗試了相對路徑和絕對路徑。最終發現需要以測試腳本自身的位置為基準，使用 `os.path.join` 來建構一個絕對路徑，才能讓 Playwright 正確找到檔案。
    *   **元素不可見**: 當操作隱藏的 `<input type="file">` 元素失敗時，我改用 Playwright 推薦的 `page.expect_file_chooser()` 方法，先點擊可見的 `<label>`，再處理彈出的檔案選擇器。
    *   **斷言失敗**: 當預期的文字沒有出現時，我會回頭檢查相關的後端邏輯和日誌，確認資料流是否正確，並修正斷言的目標文字。

透過以上方法，我得以在沒有圖形介面的情況下，對前後端功能進行較為完整的整合測試。
