### **專案交接計畫書：修復 AI 報告生成與系統優化**

**TO:** 下一位專案助理
**FROM:** Jules (架構師/顧問)
**DATE:** 2025-08-31
**SUBJECT:** 關於修復 #903 AI 報告生成問題的狀態交接與後續執行計畫

---

#### **1. 專案背景與目標**
本次任務的核心目標是解決系統的「AI 轉報告」功能異常，並進行全面的中文本土化。主要問題點如下：
*   **功能錯誤**：AI 報告生成程序會無預警地卡住（掛起），導致任務永遠停留在「處理中」。
*   **內容錯誤**：即使報告有時能生成，其標題也是空的（顯示為「無標題報告」）。
*   **本土化需求**：需要將介面上的 `pending`、`completed` 等狀態文字，以及相關標題統一為繁體中文。

---

#### **2. 已完成工作總結**
在我接手期間，已完成以下工作，為後續的除錯打下了堅實的基礎：
1.  **全面本土化**：
    *   已修改前端檔案 (`src/static/mp3.html`)，將靜態標題「進行中任務」更新為「處理中任務」。
    *   已修改所有後端檔案（`database.py`, `api_server.py`, `tools/*.py`），將任務狀態 `pending` 和 `completed` 分別更新為 `處理中` 和 `已完成`。
2.  **測試基礎建設**：
    *   編寫了一個全新的、涵蓋使用者所有需求的端對端（E2E）測試腳本：`src/tests/e2e_youtube_report_full.spec.cjs`。
    *   編寫了針對核心 AI 處理邏輯的單元測試：`src/tests/test_gemini_processor_logic.py`。
    *   為 E2E 測試新增了資料庫自動清理功能，確保測試環境的穩定與可重複性。
3.  **初步錯誤修復**：
    *   **修復 I/O 死鎖**：修改了 `api_server.py`，將其呼叫子程序的方式從可能引發死鎖的逐行讀取，改為更穩健的 `communicate()` 方法。
    *   **調整 API 超時**：修改了 `gemini_processor.py`，將對 Google AI 的請求超時從極長的時間（如 60 分鐘）縮短為較合理的 300 秒。
    *   **增加上傳超時**：為 `gemini_processor.py` 中的**檔案上傳**步驟，補上了之前遺漏的超時設定。

---

#### **3. 目前狀況與核心問題分析**
儘管進行了上述修復，但在執行最終的完整 E2E 測試時，程序**仍然被卡住**，並在等待數分鐘後超時失敗。

**核心問題分析**：
我判斷，問題的根源在於 `gemini_processor.py` 中對 Google API 函式庫的某個網路呼叫（很可能是 `upload_file` 或 `generate_content`），在特定情況下**沒有遵守我們設定的超時（timeout）限制**，從而導致了無限期的等待。我之前的修復方向是正確的，但可能需要更強硬的手段來確保超時。

---

#### **4. 建議的後續執行計畫 (for Next Assistant)**
我的建議是，不要再盲目地進行猜測和修復，而是採用更精準的除錯策略來定位問題。

##### **Phase 1: 精準定位問題根源 (Pinpoint the Root Cause)**
*   **Action**：在 `api_server.py` 的 `trigger_youtube_processing` 函式，以及 `gemini_processor.py` 的 `process_audio_file` 函式中的每一個關鍵步驟（例如：開始子程序、呼叫 `upload_file`、呼叫 `generate_content` 等）**前後**，都加上詳細的日誌記錄 (`log.info(...)`)。
*   **Example Logs**：`log.info("正要開始上傳檔案...")`、`log.info("檔案上傳成功。")`、`log.info("正要生成摘要...")`、`log.info("摘要生成完畢。")`
*   **Execution**：執行一個**簡化版**的 Playwright 測試，只處理一個 URL，以便快速重現問題。
*   **Goal**：觀察日誌輸出，找到**最後一條成功輸出的日誌**。它下一行的程式碼，就是造成整個程序卡住的元兇。

##### **Phase 2: 解決阻塞問題 (Resolve the Blocking Issue)**
*   **Action**：針對上一階段找到的阻塞函式，實施一個**更強硬的超時機制**。
*   **Recommended Method**：使用 Python 的 `concurrent.futures.ThreadPoolExecutor`。將有問題的函式（例如 `upload_file`）放到一個執行緒中去跑，然後在主執行緒中使用 `future.result(timeout=300)` 來等待結果。這個 `timeout` 參數是強制性的，可以確保即使函式庫本身卡住，我們的程式也能在 300 秒後拋出 `TimeoutError` 例外並繼續執行，而不是被永久掛起。
*   **Goal**：確保程式在任何情況下都不會無限期等待，徹底解決卡住的問題。

##### **Phase 3: 完整功能驗證 (Full Feature Verification)**
*   **Action**：在確認阻塞問題已解決後，完整地執行 `src/tests/e2e_youtube_report_full.spec.cjs` 這個我們已經寫好的端對端測試。
*   **Goal**：
    1.  驗證測試能**完整地執行完畢並通過**。
    2.  確認所有功能（包括多 URL 處理、正確的報告標題、UI 元素、中文狀態文字等）都符合使用者最初的詳細要求。
    3.  測試通過後，產生 `e2e_youtube_report_full_success.jpg` 截圖。

---

#### **5. 附錄：相關檔案列表**
*   **主要邏輯**：`src/api/api_server.py`, `src/tools/gemini_processor.py`
*   **資料庫**：`src/db/database.py`, `src/db/client.py`, `src/db/manager.py`
*   **前端介面**：`src/static/mp3.html`
*   **主要測試案例**：`src/tests/e2e_youtube_report_full.spec.cjs`
