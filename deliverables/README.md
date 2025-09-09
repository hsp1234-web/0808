# 專案重構與功能新增總結報告

**核心目標**：我們成功地將一個功能強大但單一的 Colab Jupyter Notebook，重構成為一個結構清晰、模組化、且更穩健的自動化處理系統。

我們解決了兩個核心問題：
1.  **建立了從檔案下載到內容提取的可靠流程。**
2.  **攻克了在伺服器環境中生成包含正確中文字體 PDF 報告的難題。**

以下是我們新增及修改的核心功能模組：

---

## 1. 核心工具模組 (位於 `src/tools/`)

這四個模組是我們新系統的基石，各自負責一項獨立且明確的任務。

*   **`drive_downloader.py` - 智慧下載器**
    *   **功能**：提供 `download_file()` 函式，能夠智慧地處理來自 Google Drive 的分享連結，無論是直接的檔案連結 (`/file/...`) 還是 Google 文件 (`/document/...`)，都能準確地將其下載為 PDF 檔案。
    *   **如何使用**：`download_file(url, output_dir, file_name)`

*   **`pdf_parser.py` - PDF 解析器**
    *   **功能**：提供 `parse_pdf()` 函式，使用 `PyMuPDF` 套件來讀取一個 PDF 檔案，並從中分離出所有的**純文字內容**和**內嵌的圖片**。它會將圖片單獨存檔，並回傳文字和圖片路徑列表。
    *   **如何使用**：`parse_pdf(pdf_path, image_output_dir)`

*   **`report_generator.py` - 報告產生器 (包含字體解決方案)**
    *   **功能**：這是解決中文亂碼問題的核心。
        *   `setup_font()`: 一個「智慧字體安裝器」。它會自動從可靠的來源下載 `Noto Sans TC`（思源黑體）字體，並使用 `sudo` 權限將其安裝到系統中，確保 `weasyprint` 能找到它。
        *   `generate_pdf_report()`: 接收處理好的資料（文字、圖片），將其組合成 HTML，並呼叫 `weasyprint` 生成一份圖文並茂、**中文顯示完全正常**的 PDF 報告。
    *   **如何使用**：`setup_font()` (通常在流程開始時呼叫一次)，`generate_pdf_report(data, output_path)`

*   **`gemini_manager.py` - AI 核心管理器**
    *   **功能**：這是與 Google Gemini API 溝通的唯一窗口。
        *   它能管理您的 API 金鑰，並在未來支援多金鑰輪換和錯誤重試。
        *   `analyze_text()`: 接收純文字，呼叫 AI 進行摘要和關鍵字提取。
        *   `describe_image()`: 接收單張圖片，呼叫 AI 進行內容描述和圖表類型判斷。
    *   **如何使用**：先用您的 API 金鑰初始化 `GeminiManager` 類別，然後呼叫其下的方法。

---

## 2. 資料庫升級 (位於 `src/db/`)

*   **`database.py`**：
    *   **新增資料表**：我們新增了 `documents` 和 `extracted_assets` 兩張表，用於未來結構化地儲存每個來源文件的處理狀態、雜湊值、原始文字、AI 摘要以及提取出的所有圖片和其對應的 AI 描述。
    *   **新增函式**：加入了 `add_document`, `check_document_exists_by_hash` 等一系列新函式來操作這些新表。
*   **`manager.py`**：
    *   已將所有上述的新資料庫函式，註冊到 `ACTION_MAP` 中，使其可以被系統的其他部分安全地呼叫。

---

## 3. 總指揮官 (位於 `scripts/`)

*   **`run_processing_pipeline.py`**：
    *   **功能**：這是我們目前用於展示和測試的「總指揮官」腳本。它完美地演示了如何將上述所有模組串聯起來，執行一個完整的端到端任務：從給定一個 URL 列表開始，到為每個文件產出 AI 分析結果為止。
    *   **如何執行**：`python scripts/run_processing_pipeline.py`
    *   **如何配置**：您只需在此腳本的頂部，將 `API_KEY` 變數替換為您自己的金鑰即可。

---

## 總結

我們現在擁有一個模組化的、可擴充的基礎架構。未來，無論是想加入新的 AI 分析功能（例如情緒分析、股票代碼關聯），還是想將結果儲存到資料庫，或是對接一個網頁前端，都可以在這個堅實的基礎上輕鬆進行。
