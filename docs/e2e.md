# 📖 端對端 (E2E) 測試指南

**文件作者：** Jules (AI 軟體工程師)
**最後更新：** 2025年8月14日

---

## 一、 測試框架簡介

本專案的前端使用者介面 (UI) 端對端測試採用 **Playwright** 框架。測試案例使用 **JavaScript** 編寫，存放於 `src/tests/` 目錄下，並以 `.spec.js` 為副檔名。

這些測試旨在模擬真實使用者在瀏覽器中的操作，以驗證 `src/frontend/index.html` 頁面上的各項功能是否如預期般運作。

---

## 二、 如何執行 E2E 測試

執行 E2E 測試的流程已被大幅簡化。您只需要在兩個不同的終端中，分別啟動應用程式和執行測試指令。

### **步驟 1: 啟動應用程式**

我們提供了一個統一的啟動腳本，它會處理所有依賴安裝、前端建置和後端服務啟動。

在您的第一個終端視窗中，執行以下指令：
```bash
# 此指令會準備好所有環境並啟動伺服器
python3 scripts/run_for_playwright.py
```
等待直到您看到 `✅✅✅ API 伺服器已就緒！ ✅✅✅` 的訊息。此時，應用程式正在 `http://127.0.0.1:42649` 上運行。請**保持此終端視窗開啟**。

### **步驟 2: 執行 Playwright 測試**

打開**一個新的終端視窗**，執行以下指令來啟動所有測試：

```bash
# 執行所有位於 src/tests/ 目錄下的 .spec.js 測試
npx playwright test
```

如果您只想執行特定的測試檔案，可以指定其路徑：
```bash
npx playwright test src/tests/e2e-full-ui-validation.spec.js
```

### **步驟 3: 查看測試報告**

測試執行完畢後，Playwright 會在終端中顯示結果。您也可以執行以下指令來查看一個詳細的、互動式的 HTML 報告：

```bash
npx playwright show-report
```

---

## 三、 環境準備 (僅限首次執行)

`run_for_playwright.py` 腳本會自動處理 Python (`pip`) 和 Node.js (`bun`) 的依賴安裝。但在極少數情況下，如果 Playwright 的瀏覽器執行檔遺失，您可能需要手動安裝它們：

```bash
# (僅在需要時執行) 安裝 Playwright 所需的瀏覽器
npx playwright install
```

---

## 四、 疑難排解

*   **測試無法連線到 `http://127.0.0.1:42649`**:
    *   請確認您已在第一個終端視窗中成功啟動了 `run_for_playwright.py`，並且沒有提前關閉它。
    *   檢查第一個終端的輸出，確保您看到了「API 伺服器已就緒」的訊息，並且沒有任何錯誤。
*   **測試因找不到元素而失敗**:
    *   這可能表示前端程式碼有 BUG，或是測試腳本本身已過時。
    *   您可以使用 `npx playwright test --ui` 來啟動 Playwright 的 UI 模式，這可以幫助您一步步地、視覺化地偵錯測試過程。
