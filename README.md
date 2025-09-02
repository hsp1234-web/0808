# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

[![zh-Hant](https://img.shields.io/badge/language-繁體中文-blue.svg)](README.md)

這是一個高效、可擴展的音訊轉錄與媒體處理專案，旨在提供一個功能豐富的 Web 操作介面。專案目前支援本地音訊檔案轉錄、多來源媒體下載，以及整合了 Gemini AI 的 YouTube 影片分析報告功能。

**重要提示**: 本專案正在進行一次**前端架構重構**，目標是從目前的單頁應用 (SPA) 遷移至多頁應用 (MPA) 架構。目前的開發重點是建立一套全面的端對端 (E2E) 測試套件，以確保在重構過程中的功能穩定性。

---

## ⚡️ 如何啟動與測試

請依照以下步驟設定您的開發環境並執行測試。

### 步驟 1: 安裝依賴

本專案同時使用 Node.js 和 Python，請確保兩者都已安裝。

1.  **安裝 Node.js 依賴**:
    ```bash
    bun install
    ```

2.  **安裝 Python 依賴**:
    ```bash
    # (可選) 建議在虛擬環境中執行
    # python -m venv .venv && source .venv/bin/activate
    uv pip install -r requirements/server.txt
    uv pip install -r requirements/transcriber.txt
    uv pip install -r requirements/youtube.txt
    uv pip install -r requirements/gemini.txt
    ```

3.  **安裝 Playwright 瀏覽器**:
    ```bash
    npx playwright install --with-deps
    ```

### 步驟 2: 啟動測試伺服器

為了進行前端開發或執行 Playwright 測試，您需要啟動一個專為此目的設計的後端伺服器。

```bash
# 此指令會啟動所有必要的後端服務
python3 scripts/run_server_for_playwright.py
```
伺服器成功啟動後，前端介面將可透過 `http://127.0.0.1:42649` 訪問。

### 步驟 3: 執行端對端 (E2E) 測試

本專案使用 Playwright 進行端對端測試。所有測試都在模擬 API (`API_MODE=mock`) 的模式下執行，以確保測試的穩定性和獨立性。

```bash
# 執行所有 E2E 測試
npm run test:e2e

# 或者，執行一個特定的測試檔案
# (將 <test_file_path> 替換為目標檔案的路徑)
./node_modules/.bin/cross-env API_MODE=mock GOOGLE_API_KEY='DUMMY_KEY' npx playwright test <test_file_path>
```

---

## 🧪 測試策略

我們的測試策略採用**自動化斷言**與**視覺化驗證**相結合的混合模式。

*   **自動化斷言**: 我們使用 Playwright 的 `expect` 函式來驗證 UI 元素的狀態（如可見性、文字內容、屬性等）。這是保證應用程式核心邏輯正確、可重複且高效的基石。
*   **視覺化截圖**: 在使用者請求或重大 UI 變更時，我們會擷取螢幕截圖。這不僅能作為一個直觀的「成功證明」，也有助於捕捉自動化斷言可能忽略的佈局或樣式問題。

---

## 🚀 在 Google Colab 中部署

我們提供 `colabPro.py` 腳本，方便您在 Google Colab 環境中一鍵部署和運行本專案。

**如何使用**:
1.  在 Google Colab 中開啟一個新的筆記本。
2.  將根目錄下 `colabPro.py` 的完整程式碼複製並貼到 Colab 的儲存格中。
3.  執行該儲存格。腳本將自動處理所有依賴安裝與伺服器啟動，並在完成後提供一個代理連結供您訪問。

---

## 📁 檔案結構

```
project_root/
├── config/               # 環境設定檔 (circus.ini.template)
├── docs/                 # 專案文件
├── logs/                 # 執行時產生的日誌檔案
├── requirements/         # Python 分類依賴檔案
├── scripts/              # 各類輔助腳本 (伺服器啟動器)
├── src/                  # 主要應用程式原始碼
│   ├── api/              # API 伺服器 (api_server.py)
│   ├── core/             # 核心商業邏輯 (orchestrator.py)
│   ├── db/               # 資料庫相關模組
│   ├── static/           # 靜態檔案 (HTML, CSS, 前端 JS)
│   ├── tests/            # 所有測試檔案 (E2E 測試)
│   └── tools/            # 專案使用的工具模組
├── .gitignore            # Git 忽略清單
├── AGENTS.md             # (重要) 給 AI 開發者的說明文件
├── package.json          # Node.js 專案依賴
├── playwright.config.js  # Playwright E2E 測試設定
├── pyproject.toml        # Python 專案設定
└── README.md             # 專案主說明文件
```
