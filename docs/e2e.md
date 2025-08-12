# 📖 前端 UI 端對端 (E2E) 測試指南

**文件作者：** Jules (AI 軟體工程師)
**最後更新：** 2025年8月12日

---

## 一、 測試框架簡介

本專案的前端使用者介面 (UI) 端對端測試採用 **Playwright** 框架。測試案例使用 **JavaScript** 編寫，存放於 `tests/` 目錄下，並以 `.spec.js` 為副檔名。

這些測試旨在模擬真實使用者在瀏覽器中的操作，以驗證 `static/mp3.html` 頁面上的各項功能是否如預期般運作，包括：
*   頁面基本互動 (如分頁切換、縮放)
*   媒體下載器功能
*   YouTube 報告功能
*   日誌檢視器

主要的測試檔案是 `tests/e2e-full-ui-validation.spec.js`。

---

## 二、 如何執行 UI 測試

執行 UI 測試需要兩個主要部分：**一個運作中的後端服務**，以及**執行 Playwright 測試指令**。

### 步驟 1: 環境準備 (首次執行)

如果您是第一次執行測試，需要安裝必要的依賴。

```bash
# 安裝 Node.js 依賴 (包含 Playwright)
npm install

# 安裝 Playwright 所需的瀏覽器執行檔與系統依賴
# (此指令可能需要 sudo 權限來安裝系統套件)
npx playwright install --with-deps
```

### 步驟 2: 啟動後端服務

UI 測試需要一個持續運行的後端伺服器。請勿使用 `local_run.py`，因为它會自動關閉。請使用 `circus` 來啟動服務。

```bash
# (首次執行前) 確保 logs 目錄存在
mkdir -p logs

# 在一個終端中啟動所有後端服務
python -m circus.circusd circus.ini
```
此時，API 伺服器應該會在 `http://127.0.0.1:42649` 上運行。您可以將此終端視窗保持開啟，或在背景執行它。

### 步驟 3: 執行 Playwright 測試

開啟**另一個新的終端視窗**，執行以下指令來啟動所有測試：

```bash
# 執行所有位於 tests/ 目錄下的 .spec.js 測試
npx playwright test
```

如果您只想執行特定的測試檔案，可以指定路徑：
```bash
npx playwright test tests/e2e-full-ui-validation.spec.js
```

### 步驟 4: 清理

完成測試後，您可以回到啟動 `circus` 的終端，或使用以下指令來關閉所有後端服務：
```bash
python -m circus.circusctl quit
```
---

## 三、 疑難排解

*   **`FileNotFoundError: /app/logs/...`**: 這表示您在啟動 `circus` 之前忘記建立 `logs` 目錄。請執行 `mkdir -p logs`。
*   **Playwright 測試無法連線**: 請確認您已在另一個終端中成功執行 `python -m circus.circusd circus.ini`，並且沒有看到任何錯誤訊息。您可以透過 `curl http://127.0.0.1:42649/api/health` 來確認伺服器是否正在運行。
