# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

[![zh-Hant](https://img.shields.io/badge/language-繁體中文-blue.svg)](README.md)

這是一個高效、可擴展的音訊轉錄專案，旨在提供一個可以透過 Web 介面輕鬆操作的語音轉文字服務。專案近期已整合 **YouTube 影片處理與 AI 分析** 功能，並加入了**後端驅動的 UI 狀態保存**，確保您的設定和輸入在重新整理頁面後不會遺失。

---

## ⚡️ 如何啟動與測試

本專案提供多種啟動與測試方式，以適應不同開發需求。

### 方式一：執行完整測試套件 (建議在修改後執行)

`scripts/run_tests.py` 是最權威的測試啟動器。它會準備一個乾淨的環境，啟動所有後端服務，並執行所有 Python 單元測試和 Playwright E2E 測試。

**此方式適用於**：
*   在提交程式碼前，驗證所有功能是否正常且未引入迴歸問題。
*   CI/CD 環境中的自動化測試。

**如何使用**:
```bash
# 執行所有測試
python scripts/run_tests.py

# 僅執行特定的測試檔案
python scripts/run_tests.py src/tests/e2e-full-ui-validation.spec.js
```

### 方式二：手動啟動後端服務 (用於開發與手動測試)

如果您需要一個**持續運行的後端服務**來進行前端開發或手動測試，請使用 `circus` 直接啟動。

**此方式適用於**：
*   本地端開啟 `http://127.0.0.1:42649` 進行手動功能測試。
*   獨立執行 Playwright 測試 (`./node_modules/.bin/playwright test`)。

**如何使用**:
```bash
# (首次執行前) 確保 logs 目錄存在
mkdir -p logs

# 啟動所有後端服務
python -m circus.circusd config/circus.ini

# 完成測試後，可使用以下指令關閉服務
python -m circus.circusctl quit
```
服務啟動後，您可以透過 `http://127.0.0.1:42649` 訪問前端介面。

### 方式三：在 Google Colab 中部署 (`scripts/colab.py`)

`scripts/colab.py` 是專為在 Google Colab 環境中一鍵部署和運行本專案而設計的啟動器。它會處理 Git 倉庫的複製、環境設定，並利用 Colab 的代理功能生成一個公開的訪問連結。

**如何使用**:
1.  在 Google Colab 中開啟一個新的筆記本。
2.  將 `colab.py` 的完整程式碼複製並貼到 Colab 的儲存格中。
3.  根據您的需求修改儲存格頂部的參數（例如，`TARGET_BRANCH_OR_TAG`）。
4.  執行該儲存格。儀表板將會顯示，並在伺服器就緒後提供一個 `ngrok` 或類似的代理連結供您訪問。

---

## 📈 專案狀態

**核心功能與測試 - ✅ 已完成**

*   [x] **架構重構**：已完成穩定的多程序架構（協調器、資料庫管理器、API 伺服器）。
*   [x] **功能完整**：本地檔案轉錄與 YouTube 影片處理功能均已完整實現。
*   [x] **測試穩定**：`local_run.py` 後端整合測試運作正常。前端 UI 測試採用 Playwright (`/tests` 目錄下的 `.spec.js` 檔案)，可有效驗證 `mp3.html` 的各項功能。

---
## 📁 檔案結構 (新版)

```
phoenix_transcriber/
├── .github/              # CI/CD 工作流程
├── .vscode/              # VS Code 編輯器設定
├── config/               # 所有環境設定檔 (circus.ini)
├── docs/                 # 專案文件
├── logs/                 # 執行時產生的日誌檔案
├── scripts/              # 各類輔助腳本 (部署、測試啟動器)
├── src/                  # 主要應用程式原始碼
│   ├── api/              # API 伺服器 (api_server.py)
│   ├── core/             # 核心商業邏輯 (orchestrator.py)
│   ├── db/               # 資料庫相關模組
│   ├── static/           # 靜態檔案 (HTML, CSS, 前端 JS)
│   ├── tasks/            # 背景任務/Worker (worker.py)
│   ├── tests/            # 所有測試檔案 (單元測試、E2E 測試)
│   └── tools/            # 專案使用的工具模組
├── .gitignore            # Git 忽略清單
├── package.json          # Node.js 專案依賴
├── playwright.config.js  # Playwright E2E 測試設定
├── pyproject.toml        # Python 專案設定
├── requirements.txt      # Python 專案依賴
└── README.md             # 專案主說明文件
```
