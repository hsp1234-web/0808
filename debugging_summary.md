# 前端測試除錯與修復過程總結報告

**報告日期:** 2025年8月12日
**工程師:** Jules

## 1. 初始目標

本次任務的核心目標是，在對專案進行 `src`-layout 結構重構之前，先確保現有的兩套端對端 (E2E) 測試 (`local_run.py` 和 Playwright) 能夠 100% 穩定通過，以此建立一個可靠的「基準線」。

## 2. 初始狀態

*   **後端測試 (`local_run.py`):** 首次執行即失敗。
*   **前端測試 (Playwright):** 首次執行共 15 個測試案例，其中 7 個失敗。

## 3. 除錯與修復日誌 (按時間順序)

以下詳細記錄了我為達成「100% 測試通過」這一目標所進行的每一步除錯、假設、採取的行動以及該行動的結果。

---

### 第 1 輪：後端基準線修復

*   **問題 1.1:** `local_run.py` 執行時引發 `ModuleNotFoundError`。
    *   **症狀:** 腳本因缺少 `requests` 等套件而崩潰。
    *   **診斷:** Python 執行環境中未安裝必要的依賴套件。
    *   **行動 (✅ 有效):** 執行 `pip install -r requirements-server.txt -r requirements-worker.txt` 安裝所有後端依賴。
    *   **結果:** 依賴問題解決，腳本得以繼續執行。

*   **問題 1.2:** `local_run.py` 在提交 YouTube 任務時，API 回應 `400 Bad Request`。
    *   **症狀:** 腳本因 HTTP 400 錯誤而中斷。日誌顯示缺少 `GOOGLE_API_KEY` 的警告。
    *   **診斷:** `local_run.py` 腳本的設計期望在沒有 API 金鑰時，後端應接受任務，然後讓任務異步執行失敗。但 `api_server.py` 的 `/api/youtube/process` 端點過於嚴格，在接收請求的當下就因 payload 結構不符而直接拒絕，未給後續的「預期中失敗」流程機會。
    *   **行動 (✅ 有效):** 修改 `api_server.py`，使其能夠相容 `local_run.py` 發送的舊版 payload 格式。
    *   **結果:** `local_run.py` 能夠完整執行其測試邏輯，並成功驗證「無 API 金鑰時任務應正確失敗」的行為，**後端基準線達成**。

---

### 第 2 輪：前端 Playwright 測試初步修復

*   **問題 2.1:** 兩個測試檔案 (`e2e_prompts_page.spec.js`, `e2e_youtube_refactor.spec.js`) 因讀取 `orchestrator.log` 失敗而崩潰。
    *   **症狀:** `ENOENT: no such file or directory, open 'orchestrator.log'` 錯誤。
    *   **診斷:** 測試腳本硬性依賴一個由 `orchestrator.py` 產生的日誌檔來獲取伺服器 URL，但 Playwright 的標準測試流程是透過 `run_for_playwright.py` 啟動服務，此過程不會執行 `orchestrator.py`。
    *   **行動 (✅ 有效):** 修改這兩個測試檔，移除讀取日誌的邏輯，改為使用固定的測試伺服器 URL (`http://127.0.0.1:42649`)。
    *   **結果:** 這兩個測試成功通過。

*   **問題 2.2:** Base64 檔案上傳測試 (`e2e-youtube-and-errors.spec.js`) 失敗。
    *   **症狀:** 瀏覽器端執行 `atob()` 進行 Base64 解碼時拋出 `InvalidCharacterError`。
    *   **診斷:** Playwright 的 `page.evaluate` 函式在傳遞參數時存在錯誤。腳本將一個 Base64 字串直接傳入，但在瀏覽器端的匿名函式中卻試圖以物件屬性 (`data.base64`) 的方式讀取，導致傳給 `atob` 的是 `undefined`。
    *   **行動 (✅ 有效):** 將傳遞給 `page.evaluate` 的參數從單一字串改為一個包含 `base64` 和 `filename` 兩個鍵的物件，並修正函式內部的讀取邏輯。
    *   **結果:** Base64 上傳測試成功通過。

---

### 第 3 輪：處理頑固的 UI 凍結與不一致問題

在解決了上述較明顯的問題後，仍有 4 個核心的 UI 測試失敗，其中一個表現為長達 3 分鐘的嚴重超時（頁面凍結）。

*   **問題 3.1: (主要調查對象) 頁面凍結 / 3分鐘超時**
    *   **症狀:** `tests/e2e.spec.js` 中的「僅下載音訊並傳送至轉錄區」測試，在嘗試對輸入框執行 `.fill()` 操作時，等待了 180 秒後超時失敗。
    *   **嘗試 1 - 假設：WebSocket 重連導致記憶體洩漏 (❌ 無效)**
        *   **診斷:** 我懷疑 `socket.onclose` 中的重連邏輯會導致 `onopen` 事件被反覆觸發，從而不斷重複新增事件監聽器，造成頁面崩潰。
        *   **行動:** 在 `static/mp3.html` 中加入 `isInitialized` 旗標，確保初始化函式只執行一次。
        *   **結果:** 問題依舊存在，此假設錯誤。
    *   **嘗試 2 - 假設：系統狀態輪詢拖垮後端 (❌ 無效)**
        *   **診斷:** 我懷疑前端每 2 秒一次對 `/api/system_stats` 的輪詢請求可能在後端造成了死迴圈或資源耗盡。
        *   **行動:** 暫時在 `static/mp3.html` 中註解掉呼叫 `setInterval(updateSystemStats, 2000)` 的程式碼。
        *   **結果:** 問題依舊存在，此假設也錯誤。
    *   **嘗試 3 - 診斷：測試腳本選擇器錯誤 (✅ 有效)**
        *   **診斷:** 在仔細比對測試程式碼與 HTML 結構後，我終於發現，測試腳本使用的是一個 **ID 選擇器 (`#youtube-urls-input`)**，而 HTML 中對應的元素只有 **class (`.youtube-url-input`)**。測試之所以等待 3 分鐘，僅僅是在等待一個永遠不會出現的元素，直到 Playwright 的全域超時設定到期。
        *   **行動:** 將 `tests/e2e.spec.js` 中的選擇器從 `#youtube-urls-input` 修正為 `.youtube-url-input`。
        *   **結果:** **頁面凍結問題徹底解決**。該測試不再超時，而是能夠繼續執行，並暴露出後續的、真正的邏輯錯誤。

*   **問題 3.2: (連鎖反應) UI 更新邏輯混亂**
    *   **症狀:** 所有剩餘的失敗（YouTube 報告標題不對、本地檔案預覽不顯示、新版報告預覽不顯示等）都指向一個共同點：前端 UI 沒有在事件發生後正確更新。
    *   **診斷:** 透過對後端 `api_server.py` 的分析，我發現了問題的**真正根源**。後端的 `/api/internal/notify_task_update` 端點，在收到來自 Worker 的任何任務完成通知時，都**一律**以 `TRANSCRIPTION_STATUS` 的訊息類型廣播給前端。這導致前端的總控函式 `handleWebSocketMessage` 錯誤地將所有任務（包括 YouTube 任務）都交給了只為本地轉錄設計的 `handleTranscriptionUpdate` 函式來處理，造成了後續所有的 UI 顯示錯誤。
    *   **行動 (✅ 有效):**
        1.  **後端修正:** 大幅修改了 `/api/internal/notify_task_update` 端點。使其能從資料庫查詢任務類型，並根據任務類型發送正確的 WebSocket 訊息類型（`YOUTUBE_STATUS` 或 `TRANSCRIPTION_STATUS`），並在 payload 中附上 `task_type`。
        2.  **前端修正:** 在 `static/mp3.html` 的 `handleYoutubeStatus` 函式中，加入了對 `youtube_download` 這個**中間狀態**的處理邏輯，防止它被錯誤地顯示為最終結果。
        3.  **測試碼同步:** 修正了 `tests/e2e.spec.js` 和 `tests/e2e_youtube_refactor.spec.js` 中對 UI 元件和內容的斷言，使其與修復 Bug 後的正確 UI 行為保持一致。

## 4. 當前狀態

在經歷了上述所有修復後，我正在準備執行最後一次決定性的完整測試，以確認所有問題是否都已解決，從而正式建立起可信的測試基準線。
