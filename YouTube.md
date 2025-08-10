# YouTube 影片處理功能整合計畫書

本文檔旨在詳細記錄將「YouTube 影片處理與 AI 分析」功能整合至現有音訊轉錄儀專案的完整開發計畫與當前進度。

## 專案目標

將使用者在 Colab 中設計的 YouTube 影片處理流程（下載音訊 -> Gemini AI 分析 -> 生成 HTML 報告）無縫整合到現有的「Web 前端 + 異步任務後端」架構中，並提供一個直觀易用的網頁操作介面。

## 整體架構設計

我們將遵循專案現有的優秀架構，將新功能模組化為可獨立測試的後端工具，並由主應用程式 `api_server.py` 進行協調。

-   **後端工具 (`tools/`)**: 建立 `youtube_downloader.py` 和 `gemini_processor.py` 兩個獨立的命令列工具，分別負責「YouTube 音訊下載」和「Gemini AI 處理與報告生成」。
-   **API 伺服器 (`api_server.py`)**: 新增 API 端點 (`/api/process_youtube`) 來接收前端請求，並在獨立執行緒中協調上述兩個工具的執行。
-   **WebSocket 通訊**: 擴充現有的 WebSocket，使其能夠即時回報 YouTube 處理流程中的各種狀態（如：下載中、AI 分析中、完成等）。
-   **前端介面 (`static/mp3.html`)**: 新增一個專屬的功能分頁，讓使用者可以貼上網址、選擇模型、啟動任務，並在頁面上預覽最終生成的 HTML 報告。

---

## 詳細開發計畫與進度

### 第一階段：後端基礎建設與工具化
**狀態： ✅ 已完成**

此階段的目標是將核心邏輯轉化為符合現有專案架構的、可重複使用的後端工具。

-   [x] **修改 `requirements.txt`**: 新增 `pytubefix`, `google-generativeai`, `pydub` 等依賴套件。
-   [x] **建立 `tools/youtube_downloader.py`**: 一個獨立的命令列工具，負責從 YouTube 下載音訊並以 JSON 格式回報進度與結果。
-   [x] **建立 `tools/gemini_processor.py`**: 一個獨立的命令列工具，負責接收音訊檔案、呼叫 Gemini API 進行分析，並生成最終的 HTML 報告。

### 第二階段：擴充後端 API 與主邏輯
**狀態： ✅ 已完成**

此階段的目標是擴充 `api_server.py` 來串聯整個後端流程。

-   [x] **新增 API 端點**: 在 `api_server.py` 中建立了 `POST /api/process_youtube` 端點，用於接收前端請求並在資料庫中建立任務。
-   [x] **整合處理流程**: 在 `api_server.py` 中建立了 `trigger_youtube_processing` 函式。此函式會在背景執行緒中，依序呼叫 `youtube_downloader.py` 和 `gemini_processor.py`，實現完整的處理流程。
-   [x] **擴充 WebSocket**: 在 `api_server.py` 的 WebSocket 邏輯中，新增了對 `START_YOUTUBE_PROCESSING` 訊息的處理，使其能夠觸發 `trigger_youtube_processing` 函式，並即時廣播處理進度與最終結果。

### 第三階段：打造全新前端介面
**狀態： ⏳ 進行中**

此階段的重點是修改 `static/mp3.html`，為新功能提供一個直觀易用的操作介面。

-   [x] **新增 HTML/CSS 骨架**: 已在 `static/mp3.html` 中加入了分頁導覽列的 HTML 結構與對應的 CSS 樣式。
-   [ ] **開發前端互動邏輯**:
    -   [ ] 編寫 JavaScript 程式碼來實現分頁切換效果。
    -   [ ] 開發 YouTube 功能區塊的互動邏輯，包括：
        -   呼叫後端 API 來動態載入 Gemini 模型列表。
        -   當使用者點擊「開始處理」時，呼叫 `/api/process_youtube` 端點來建立任務。
        -   接收到任務 ID 後，透過 WebSocket 發送 `START_YOUTUBE_PROCESSING` 訊息來啟動處理。
        -   監聽 WebSocket 傳來的各種進度訊息，並即時更新 UI。
        -   處理完成後，在檔案列表中顯示可下載/預覽的結果。
        -   實現 HTML 報告的頁內預覽功能。

### 第四階段：測試與驗證
**狀態： 尚未開始**

在完成所有開發後，將進行嚴格的測試以確保新舊功能的穩定性。

-   [ ] **回歸測試**: 執行專案現有的端對端（E2E）測試，確保對 `mp3.html` 的修改沒有破壞原本的本地檔案上傳轉錄功能。
-   [ ] **新功能驗證**: 編寫一個新的前端驗證腳本，模擬操作 YouTube 功能的完整流程，並產生一張螢幕截圖以證明功能正常運作。
-   [ ] **提交成果**: 在所有測試通過後，提交所有程式碼變更。
