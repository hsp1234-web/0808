# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

歡迎使用鳳凰音訊轉錄儀，一個強大的、網頁介面的音訊與視訊轉錄工具。本應用程式整合了後端處理、前端互動介面與自動化測試，旨在提供一個高效、易用的轉錄解決方案。

## 主要技術棧

*   **後端**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
*   **前端**: 原生 JavaScript, [Tailwind CSS](https://tailwindcss.com/)
*   **打包與建置**: [Bun](https://bun.sh/)
*   **測試**: [Playwright](https://playwright.dev/)

## 專案結構

本專案的核心邏輯位於 `src` 目錄下，整體結構如下：

```
.
├── src/
│   ├── api/                # FastAPI 後端伺服器
│   ├── core/               # 核心業務邏輯 (例如，任務協調器)
│   ├── db/                 # 資料庫管理與客戶端
│   ├── frontend/           # 前端原始碼 (HTML, JS, CSS)
│   │   ├── components/     # 前端 JS 元件
│   │   ├── index.html      # 主入口 HTML
│   │   └── main.js         # 主入口 JavaScript
│   ├── static/             # 靜態檔案
│   │   └── dist/           # 打包後的前端資源 (由 build 產生)
│   ├── tasks/              # 背景任務工作者
│   ├── tests/              # 自動化測試 (包含 Playwright E2E 測試)
│   └── tools/              # 外部工具的封裝 (例如，轉錄器、下載器)
│
├── scripts/                # 用於啟動、測試的實用腳本
│   └── run_for_playwright.py # 啟動完整應用程式 (後端+前端) 的主要腳本
│
├── docs/                   # 專案文件
│   └── ARCHITECTURE.md     # 架構說明文件
│
├── package.json            # Node.js 依賴與腳本
├── requirements.txt        # Python 依賴
└── tailwind.config.js      # Tailwind CSS 設定檔
```

## 如何運行應用程式

啟動本專案以進行開發或測試的最推薦方式是使用 `run_for_playwright.py` 腳本。這個腳本會自動處理所有必要的步驟。

在專案根目錄下執行以下指令：

```bash
python3 scripts/run_for_playwright.py
```

此指令將會：
1.  **安裝依賴**：安裝所有必要的 Python (`requirements.txt`) 和 Node.js (`package.json`) 依賴。
2.  **建置前端**：執行 `bun run build` 來編譯 Tailwind CSS 和打包 JavaScript。
3.  **清理環境**：刪除舊的日誌和資料庫檔案，確保一個乾淨的啟動環境。
4.  **啟動服務**：依序啟動資料庫管理器和 FastAPI 後端伺服器。

當您在終端機看到 `✅✅✅ API 伺服器已就緒！ ✅✅✅` 的訊息時，表示應用程式已成功啟動。

預設情況下，您可以透過瀏覽器訪問 `http://127.0.0.1:42649` 來使用此應用程式。

## 前端開發

如果您需要專注於前端開發，可以使用 `package.json` 中定義的腳本：

*   **建置所有資源**:
    ```bash
    bun run build
    ```
*   **僅監控 JavaScript 變動並自動打包**:
    ```bash
    bun run watch
    ```

**注意**: 這些指令只會處理前端資源的打包，您仍需另外啟動後端伺服器來查看完整的應用程式。因此，在大多數情況下，直接使用 `scripts/run_for_playwright.py` 是更方便的選擇。
