# 📖 前端 UI 端對端 (E2E) 測試指南

**文件作者：** Jules (AI 軟體工程師)
**最後更新：** 2025年8月14日

---

## 一、 測試框架簡介

本專案的前端使用者介面 (UI) 端對端測試採用 **Playwright** 框架。測試案例使用 **JavaScript** 編寫，存放於 `src/tests/` 目錄下，並以 `.spec.js` 為副檔名。

這些測試旨在模擬真實使用者在瀏覽器中的操作，以驗證 `static/mp3.html` 頁面上的各項功能是否如預期般運作。主要的測試檔案是 `src/tests/e2e-full-ui-validation.spec.js`。

---

## 二、 如何執行 UI 測試

我們強烈建議使用專案提供的**統一測試啟動器** `scripts/run_tests.py` 來執行所有測試，包括 E2E 測試。此腳本會自動處理所有繁瑣的步驟。

### 建議方式：使用統一測試啟動器

`scripts/run_tests.py` 會自動完成以下所有事情：
1.  安裝所有 Python 和 Node.js 依賴 (`bun install`)。
2.  清理舊的程序和資料庫檔案。
3.  使用 `circus` 在背景啟動所有必要的後端服務。
4.  等待後端服務完全就緒。
5.  執行所有 `pytest` 和 `playwright` 測試。
6.  在測試結束後，自動關閉所有背景服務。

**如何使用**:
```bash
# 執行所有測試 (包含 E2E)
python scripts/run_tests.py

# 僅執行特定的 E2E 測試檔案
python scripts/run_tests.py src/tests/e2e-full-ui-validation.spec.js
```

### 備用方式：手動執行

如果您因特殊原因需要手動執行，步驟如下。

**步驟 1: 環境準備 (首次執行)**

```bash
# 安裝 Python 依賴
pip install -r requirements.txt

# 安裝 Node.js 依賴 (包含 Playwright)
bun install
```

**步驟 2: 啟動後端服務**

```bash
# (首次執行前) 確保 logs 目錄存在
mkdir -p logs

# 在一個終端中啟動所有後端服務
python -m circus.circusd config/circus.ini
```

**步驟 3: 執行 Playwright 測試**

開啟**另一個新的終端視窗**，執行以下指令：

```bash
# 執行所有測試
./node_modules/.bin/playwright test

# 或僅執行特定檔案
./node_modules/.bin/playwright test src/tests/e2e-full-ui-validation.spec.js
```

**步驟 4: 清理**

測試結束後，回到啟動服務的終端，或使用以下指令關閉服務：
```bash
python -m circus.circusctl quit
```
---

## 三、 疑難排解

*   **`FileNotFoundError: /app/logs/...`**: 這表示您在啟動 `circus` 之前忘記建立 `logs` 目錄。請執行 `mkdir -p logs`。
*   **Playwright 測試無法連線**: 請確認您已在另一個終端中成功執行 `python -m circus.circusd config/circus.ini`，並且沒有看到任何錯誤訊息。您可以透過 `curl http://127.0.0.1:42649/api/health` 來確認伺服器是否正在運行。
*   **`bun test` 相關錯誤**: 請勿使用 `bun test`。本專案的測試應透過 `scripts/run_tests.py` 或直接呼叫 `playwright` 執行器來啟動。
