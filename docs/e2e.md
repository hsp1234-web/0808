# 📖 前端 UI 端對端 (E2E) 測試指南

**文件作者：** Jules (AI 軟體工程師)
**最後更新：** 2025年8月15日

---

## 一、 測試框架簡介

本專案的前端使用者介面 (UI) 端對端測試採用 **Playwright** 框架。測試案例使用 **JavaScript** 編寫，存放於 `tests/` 目錄下，並以 `.spec.js` 為副檔名。

這些測試旨在模擬真實使用者在瀏覽器中的操作，以驗證 `static/mp3.html` 頁面上的各項功能是否如預期般運作。

主要的測試檔案是 `tests/e2e-full-ui-validation.spec.js`。

---

## 二、 如何執行 UI 測試 (新版流程)

過去，執行 UI 測試需要手動安裝多種依賴、啟動後端服務、然後再執行測試指令。這個過程繁瑣且容易出錯。

現在，我們引入了一個統一的**環境設定與驗證腳本**，極大地簡化了這個流程。

### 步驟 1: 環境設定與驗證 (推薦的唯一入口)

無論您是首次設定環境，還是想要執行任何測試，都請先從這個指令開始。它會處理所有事情。

```bash
# 此指令會安裝所有依賴 (Python & Node.js)、啟動伺服器、
# 擷取一張快照以驗證 UI 可達性，然後自動關閉所有服務。
bun run snapshot
```

**請務必先成功執行此指令。** 如果 `bun run snapshot` 成功，代表您的環境已準備就緒，可以執行更具體的 Playwright 測試。

關於此指令的詳細說明，請參閱根目錄下的 **`AGENTS.md`** 文件。

### 步驟 2: 執行特定的 Playwright 測試

在成功執行過 `bun run snapshot` 後，您的後端伺服器和環境已經被證明是可用的。現在，您可以手動啟動後端服務，並執行完整的 E2E 測試套件。

**1. 啟動後端服務**

在一個終端中，使用 `circus` 啟動一個持續運行的後端服務。

```bash
# 確保您位於專案根目錄
python -m circus.circusd circus.ini
```

**2. 執行 Playwright 測試**

開啟**另一個新的終端視窗**，執行 Playwright 指令。

```bash
# 執行所有 UI 測試
npx playwright test

# 或僅執行某個特定的測試檔案
npx playwright test tests/e2e-full-ui-validation.spec.js
```

### 步驟 3: 清理

測試完成後，關閉後端服務：
```bash
python -m circus.circusctl quit
```

---

## 三、 疑難排解

由於新的 `snapshot` 腳本處理了大部分舊的環境問題，現在的疑難排解更為簡單：

*   **`bun run snapshot` 失敗**:
    *   這是最根本的問題。請仔細閱讀該指令輸出的錯誤日誌。
    *   **不要**嘗試手動執行 `npm install` 或 `pip install`。`snapshot` 腳本的失敗通常指向更深層的設定問題。
    *   請依序檢查 `AGENTS.md` 中提到的「重要文件檢查清單」，特別是 `circus.log` 和 `api_server.err`。

*   **`npx playwright test` 失敗，但 `snapshot` 成功**:
    *   這表示您的基礎環境是好的，但問題出在 E2E 測試腳本 (`*.spec.js`) 的邏輯本身。
    *   使用 Playwright 的 UI 模式來進行互動式除錯，這非常有效：
        ```bash
        npx playwright test --ui
        ```
