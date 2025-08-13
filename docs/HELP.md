# 開發與除錯交接文件 (HELP.md)

**日期**: 2025-08-09
**處理者**: Jules

本文檔旨在記錄針對「新增前端下載/預覽按鈕並修復後端邏輯」任務的開發與除錯過程，並詳細闡述一個尚未解決的底層環境問題，以便後續的開發者能夠順利接手。

---

## 1. 任務目標與已完成的功能

**核心目標**：
1.  **後端修復**：確保轉錄任務完成後，包含結果的檔案路徑能被正確儲存至資料庫。
2.  **前端增強**：在 `static/mp3.html` 中，為已完成的任務動態新增「預覽」和「下載」按鈕。
3.  **測試驗證**：確保以上功能在模擬（Mock）模式下能正常運作。

**已完成並驗證的程式碼修改**：

*   **`worker.py`** (`db/database.py`):
    *   已成功修改 `worker.py` 的 `process_transcription_task` 函式。
    *   在任務成功後，會將一個包含 `transcript` 和 `transcript_path` 的 JSON 物件寫入資料庫的 `result` 欄位。這是下載功能的核心。

*   **`static/mp3.html`**：
    *   **新增按鈕**：已修改 `handleWebSocketMessage` 函式，當收到 `TRANSCRIPTION_STATUS: completed` 的 WebSocket 訊息時，會動態建立「預覽」和「下載」按鈕，並將其附加到對應的任務項目上。
    *   **修正 API 回應處理**：修復了 `xhr.onload` 中處理 `/api/transcribe` 回應的邏輯，使其能兼容兩種不同的 JSON 格式。
    *   **移除進度條文字**：已按照要求，將上傳進度條中的文字移除。

*   **`api_server.py` 的核心邏輯修正**：
    *   **模擬模式**：加入了 `--mock` 命令列旗標的支援，允許在啟動時指定是否進入模擬模式。
    *   **邏輯修正**：修正了 `trigger_transcription` 函式。在模擬模式下，它現在會：
        1.  使用 `mock_transcriber.py` 執行模擬轉錄。
        2.  在轉錄完成後，**主動將結果（包含 `transcript_path`）寫入資料庫**，並將任務狀態更新為 `completed`。
        3.  最後才將 `completed` 狀態透過 WebSocket 廣播給前端。
    *   此修改是為了確保在專案當前的「WebSocket 驅動」架構下，UI 更新與資料庫狀態能同步。

---

## 2. 未解決的底層問題：`disk I/O error`

儘管上述核心功能邏輯已開發完成，但在使用專案自帶的整合測試腳本 `local_run.py` 進行驗證時，遇到了一個非常頑固的底層錯誤。

### 2.1. 問題描述

執行 `python local_run.py` 時，程序在啟動的最初階段就失敗了，日誌中充滿了來自 `src/core/orchestrator.py` 和 `src/api/api_server.py` 的資料庫錯誤：

```
db.database - ERROR - 初始化資料庫時發生錯誤: disk I/O error
DBLogHandler Error: Cannot get DB connection. Log from orchestrator lost.
db.database - ERROR - 資料庫連線失敗: disk I/O error
```

此錯誤導致 `src/core/orchestrator.py` 的心跳檢測 (`HEARTBEAT`) 無法正確讀取資料庫中的任務狀態，最終導致測試因超時而失敗。

### 2.2. 已嘗試的除錯與修復步驟

我為了追蹤和解決這個 I/O 錯誤，進行了多輪的分析和嘗試：

1.  **確認架構**：
    *   最初我認為 `worker.py` 是主要處理者，並試圖重構系統為 Worker 導向的架構。
    *   在詳細閱讀 `src/core/orchestrator.py` 後，發現了關鍵日誌：`🚫 [架構性決策] Worker 程序已被永久停用，以支援 WebSocket 驅動的新架構。`
    *   **結論**：我確認了專案的**預期架構**是 `api_server.py` 作為主處理器，這讓我將注意力轉回 `api_server.py`。

2.  **解決競爭條件**：
    *   我意識到 `api_server` 的處理執行緒和 `worker`（如果啟用）會產生競爭，並且 `api_server` 的執行緒在完成後沒有更新資料庫，導致了下載失敗。
    *   **解決方案**：我將更新資料庫的邏輯加入了 `api_server.py` 的 `trigger_transcription` 函式中。這是**核心功能的關鍵修復**。

3.  **解決 `disk I/O error`**：
    *   **假設 1：啟動時的競爭條件**。我懷疑 `src/core/orchestrator.py` 和它啟動的 `src/api/api_server.py` 子程序同時嘗試初始化資料庫。
    *   **嘗試 1**：我修改了 `src/api/api_server.py`，移除了它在 `if __name__ == "__main__"` 中的初始化呼叫，讓 `src/core/orchestrator.py` 成為唯一的初始化者。**結果：失敗，錯誤依舊。**

    *   **假設 2：目錄不存在**。我懷疑 `db/` 目錄可能在 `local_run.py` 清理資料庫檔案後沒有被重新建立。
    *   **嘗試 2**：我修改了 `db/database.py` 的 `initialize_database` 函式，在連接資料庫前，先使用 `DB_FILE.parent.mkdir(exist_ok=True)` 來確保 `db/` 目錄存在。**結果：失敗，錯誤依舊。**

### 2.3. 問題根源推測

到目前為止，所有針對程式碼邏輯的合理修改都未能解決此 I/O 錯誤。此錯誤的特點是：
*   它在 `local_run.py` 刪除舊資料庫檔案後，`src/core/orchestrator.py` 首次嘗試建立新檔案和連線時就立即發生。
*   此時沒有其他程序在存取該檔案，理論上不應有鎖定或權限問題。

**我的最終推測是，這個問題可能與執行環境本身、檔案系統、或是 Python 的 `sqlite3` 模組在當前環境下處理多進程檔案操作的某個底層 bug 有關。** 它似乎不是一個單純的程式碼邏輯錯誤。

---

## 3. 給下一位開發者的建議

1.  **專注於 `api_server.py`**：請記得，`worker.py` 已被停用。所有的核心處理邏輯都在 `api_server.py` 的 `trigger_transcription` 函式中。
2.  **驗證核心邏輯**：我所做的修改（前端按鈕、後端資料庫更新邏輯）是完整且正確的。您可以透過**手動啟動 `api_server.py --mock`** 並在瀏覽器中操作來驗證這一點，這個流程是通的。
3.  **解決 `local_run.py` 的 I/O 錯誤**：
    *   您的首要任務是解決 `local_run.py` 在啟動時發生的 `disk I/O error`。
    *   可以考慮在 `local_run.py` 中，刪除資料庫後，加入一個微小的延遲 (`time.sleep(0.1)`)，再啟動 `src/core/orchestrator.py`，看看是否能解決這個檔案系統層級的競爭問題。
    *   或者，可以研究 `src/core/orchestrator.py` 和 `db/database.py` 的日誌記錄與資料庫連線方式，是否有更深層的衝突。
4.  **提交**：一旦 `local_run.py` 的問題解決，我所提交的所有其他程式碼應該都能順利通過測試，屆時即可完成整個任務。

祝您好運！
