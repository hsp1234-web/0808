# 專案架構藍圖

本文檔闡述了「鳳凰音訊轉錄儀」專案當前的技術架構。此架構的設計目標是實現一個功能完整、易於開發與測試的全端應用程式。

---

## 1. 高層次架構

本專案是一個典型的**前後端分離的單頁應用程式 (SPA)**：

*   **後端 (Backend)**:
    *   使用 **Python** 和 **FastAPI** 框架建立，提供一個 RESTful API 和 WebSocket 服務。
    *   負責處理所有核心業務邏輯，如接收上傳檔案、管理任務佇列、與外部工具（轉錄器、下載器）互動等。
    *   位於 `src/api/`、`src/core/`、`src/db/` 等目錄下。

*   **前端 (Frontend)**:
    *   使用**原生 JavaScript** 編寫，透過元件化的方式組織程式碼。
    *   使用 **Tailwind CSS** 進行樣式設計。
    *   所有前端原始碼位於 `src/frontend/`。
    *   透過 **Bun** 進行打包和建置，產生的最終靜態檔案 (`main.js`, `output.css`) 位於 `src/static/dist/`。

*   **服務提供 (Serving)**:
    *   FastAPI 後端伺服器同時也負責提供前端靜態檔案。
    *   根路徑 `/` 提供 `src/frontend/index.html`。
    *   `/dist` 路徑提供打包後的前端資源。
    *   `/static` 路徑提供其他靜態資源。

---

## 2. 核心目錄結構

以下是當前專案最核心的目錄結構：

```
.
├── src/
│   ├── api/                # FastAPI 後端伺服器，定義所有 API 端點
│   ├── core/               # 核心業務邏輯 (目前未使用，但為未來保留)
│   ├── db/                 # 資料庫管理 (SQLite) 與客戶端邏輯
│   ├── frontend/           # 前端原始碼 (HTML, JS, CSS)
│   │   ├── components/     # 可複用的 JavaScript 元件
│   │   ├── index.html      # 前端主入口 HTML 檔案
│   │   └── main.js         # 前端主入口 JavaScript 檔案
│   ├── static/             # 存放靜態檔案
│   │   └── dist/           # 存放由 `bun run build` 產生的打包後前端資源
│   ├── tasks/              # 背景任務工作者 (目前未使用)
│   ├── tests/              # 自動化測試
│   │   └── e2e-*.spec.js   # Playwright 端對端測試案例
│   └── tools/              # 封裝外部工具的 Python 腳本
│
├── scripts/                # 開發與測試用的主要腳本
│   └── run_for_playwright.py # 開發和測試時啟動完整應用的主要入口
│
├── docs/                   # 專案文件 (例如本文件)
├── package.json            # Node.js 依賴與建置腳本
└── requirements.txt        # Python 依賴
```

---

## 3. 執行流程

### 開發與測試流程

為了簡化開發和 E2E 測試，我們使用 `scripts/run_for_playwright.py` 作為統一的啟動器。

**[開發者/CI 系統]** `->` **`python3 scripts/run_for_playwright.py`**
1.  **[腳本]** 檢查並安裝 Python 和 Node.js 的依賴。
2.  **[腳本]** 執行 `bun run build`，將 `src/frontend` 的原始碼打包到 `src/static/dist`。
3.  **[腳本]** 清理舊的日誌和資料庫，確保環境乾淨。
4.  **[腳本]** 在背景啟動資料庫管理器 (`src/db/manager.py`)。
5.  **[腳本]** 在背景啟動 FastAPI 伺服器 (`src/api/api_server.py`)。
6.  **[FastAPI]** 伺服器開始監聽請求，並提供前端介面與後端 API。
7.  **[開發者/CI 系統]** 此時可以打開瀏覽器訪問 `http://127.0.0.1:42649`，或執行 Playwright 測試。

這個流程確保了每次啟動時，前後端的程式碼都是最新的，並且在一個一致的環境中運行。
