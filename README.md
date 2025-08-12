# 鳳凰音訊轉錄儀 (Phoenix Transcriber)

[![zh-Hant](https://img.shields.io/badge/language-繁體中文-blue.svg)](README.md)

這是一個高效、可擴展的音訊轉錄專案，旨在提供一個可以透過 Web 介面輕鬆操作的語音轉文字服務。專案近期已整合 **YouTube 影片處理與 AI 分析** 功能。

---

## ⚡️ 如何啟動與測試

我們提供兩種主要的執行方式：一個用於本地開發與端對端測試，另一個專為在 Google Colab 中部署而設計。

### 方式一：自動化後端整合測試 (`local_run.py`)

`local_run.py` 是一個**自動化的整合測試腳本**，主要用於驗證後端的核心功能。它會啟動所有服務，提交一個測試任務，並在任務完成後自動關閉。

**此方式適用於**：
*   快速驗證後端修改是否引發問題。
*   在 CI/CD 環境中進行自動化檢查。

**如何使用**:
```bash
# 如果您有 Google API 金鑰，請將其設定在環境中以測試完整流程
python local_run.py
```
當腳本顯示「所有驗證均已通過！」或「任務正確地以 'failed' 狀態結束」（在沒有 API 金鑰的情況下）時，即表示後端功能運作正常。

### 方式二：啟動後端服務 (用於 UI 測試或手動操作)

如果您需要一個**持續運行的後端服務**來進行前端開發、手動測試或執行 Playwright UI 測試，請使用 `circus` 直接啟動服務。

**此方式適用於**：
*   本地端開啟 `static/mp3.html` 進行手動功能測試。
*   執行 Playwright 端對端 UI 測試。

**如何使用**:
```bash
# (首次執行前) 確保 logs 目錄存在
mkdir -p logs

# 啟動所有後端服務
python -m circus.circusd circus.ini

# 完成測試後，可使用以下指令關閉服務
python -m circus.circusctl quit
```
服務啟動後，您可以透過 `http://127.0.0.1:42649` 訪問前端介面。

### 方式三：在 Google Colab 中部署 (`colab.py`)

`colab.py` 是專為在 Google Colab 環境中一鍵部署和運行本專案而設計的啟動器。它會處理 Git 倉庫的複製、環境設定，並利用 Colab 的代理功能生成一個公開的訪問連結。

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
## 📁 檔案結構 (摘要)

```
/
|-- api_server.py        # Web 伺服器 (FastAPI)
|-- orchestrator.py      # 系統協調器
|-- local_run.py         # [主要] 本地端對端測試腳本
|-- colab.py             # Google Colab 部署腳本
|
|-- static/              # 前端資源 (mp3.html)
|-- db/                  # 資料庫模組
|-- tools/               # 核心工具 (轉錄、下載、AI處理)
|-- tests/               # Playwright 等測試碼
`-- README.md            # 本文件
```
