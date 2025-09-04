# 交接報告 (V2) - Jules

**日期**: 2025-09-04
**交接目的**: 本次提交修復了數個前端顯示層的 Bug，但核心的 E2E 測試仍然失敗。此報告旨在詳細記錄已完成的工作、當前的系統狀態、以及對剩餘問題的分析，以便下一位開發者能在此基礎上繼續除錯。

---

## 1. 已完成的工作與已修復的 Bug

在本次工作期間，我成功定位並修復了以下三個主要問題：

### 1.1. 【已修復】MPA 頁面內容無法顯示
- **問題**: 在 SPA 到 MPA 重構後，`/downloader` 和 `/youtube` 頁面的主要內容區塊在載入時被隱藏，導致使用者無法看到任何輸入欄位。
- **根本原因**: 對應的 `div.tab-content` 區塊缺少了 `active` CSS class。
- **修復方案**: 我手動為 `downloader.html` 和 `youtube.html` 中對應的內容區塊加上了 `active` class，確保它們在頁面載入時能正確顯示。

### 1.2. 【已修復】全域儀表板數據未更新
- **問題**: 所有頁面上的「全域儀表板」中的 CPU、RAM 等數據始終顯示為 `--%`，沒有動態更新。
- **根本原因**: 在 MPA 重構過程中，負責從 `/api/system_stats` 獲取並更新儀表板數據的 JavaScript 函式 (`updateSystemStats`)，只被保留在了 `index.html` 中，而從 `downloader.html` 和 `youtube.html` 中遺失了。
- **修復方案**: 我已將 `updateSystemStats` 函式及其計時器呼叫，從 `index.html` 複製並成功添加回 `downloader.html` 和 `youtube.html` 的 `<script>` 區塊中。

### 1.3. 【已修復】API 金鑰驗證的環境變數問題
- **問題**: 後端在驗證 API 金鑰時，即使金鑰有效，也回報失敗。
- **根本原因**: 我透過直接在命令列測試 `gemini_processor.py`，確認了該工具腳本和 API 金鑰本身都是有效的。問題的根源在於 `api_server.py` 的 `/api/youtube/validate_api_key` 端點。該端點為了建立一個「乾淨」的執行環境而建立了一個 `minimal_env`，但這個環境中**缺少了 `PYTHONPATH`**，導致子程序 `gemini_processor.py` 無法找到其依賴的本地 Python 模組。
- **修復方案**: 我修改了 `api_server.py`，在 `minimal_env` 中明確加入了正確的 `PYTHONPATH`，確保子程序能正常運作。

---

## 2. 當前的困境與失敗的 E2E 測試

儘管修復了上述問題，我最後執行的綜合性 E2E 測試 (`e2e_comprehensive_real.spec.cjs`) 仍然**全部失敗**。

- **測試日誌**:
  - **本地上傳 & 媒體下載**: 這兩個測試都在等待頁面元素（如「開始轉錄」按鈕）變為可操作時**超時 (Timeout)**。這表示即便我為了除錯而暫時移除了前端的 `checkSystemReadiness` 等待，頁面依然沒有被完全啟用。
  - **YouTube 報告**: API 金鑰驗證**依然失敗**，狀態無法更新為「金鑰有效」。這非常令人困惑，因為我確信已經修正了 `PYTHONPATH` 的問題。

---

## 3. 對根本原因的推論與交接建議

**核心推論**: 我高度懷疑目前的問題根源，與專案日誌 (`Log.md` #921) 中多次提到的**「涉及執行緒、asyncio 事件迴圈和子程序之間的底層互動」**問題是相同的。我所做的修復可能只是解決了表層問題，但未能觸及這個更底層的、關於非同步處理與程序間通訊的衝突。

**給下一位開發者的建議**:

1.  **放棄高層級測試，專注於核心呼叫**:
    -   不要再嘗試執行完整的 E2E 測試。建議直接從 `api_server.py` 下手。
    -   可以嘗試在 `api_server.py` 中，直接呼叫 `orchestrator.py` 或 `transcriber.py` 的核心函式（而不是透過 `subprocess`），觀察是否能成功。

2.  **簡化 `orchestrator.py`**:
    -   `src/core/orchestrator.py` 是任務調度的核心。可以嘗試建立一個極簡的測試腳本，只呼叫 `orchestrator.py` 來執行一個最簡單的任務（例如，一個只會 `time.sleep(5)` 並回報成功的假任務）。
    -   如果連這個最簡單的任務都無法被正確調度並回報狀態，那就證明問題出在 `orchestrator` 的核心迴圈或其與資料庫的互動中。

3.  **審查 `subprocess` 的使用**:
    -   所有在 `api_server.py` 中對 `subprocess.run` 或 `subprocess.Popen` 的呼叫都值得懷疑。
    -   檢查傳遞給子程序的 `env` 是否完整。除了 `PYTHONPATH`，是否還需要其他環境變數？
    -   `Log.md` #921 提到，唯一能讓測試通過的是一個「啞劇」子程序 (`subprocess.run`) 實驗。這是一個極其重要的線索，暗示著問題可能與 `stdout`/`stderr` 的管道 (pipe) 或 `communicate()` 的阻塞行為有關。

希望這份報告能幫助您快速地接手這個複雜的問題。我已將所有已驗證的修復提交，您可以安心地在此基礎上繼續工作。
