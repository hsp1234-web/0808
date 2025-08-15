# AGENTS.md - 給 AI 開發者的說明

這個專案包含一個 Python 後端和一個 Node.js/Bun 的測試與腳本環境。

## 首次設定

要設定好開發環境，請執行以下指令。這個指令會處理所有 Python 和 Node.js 的依賴，並下載 Playwright 需要的瀏覽器：

```bash
bun run snapshot
```

這個指令會執行 `package.json` 中的 `snapshot` 腳本，它包含以下步驟：
1.  `mkdir -p logs` - 建立日誌目錄。
2.  `python3 -m pip install -r requirements.txt` - 安裝 Python 依賴。
3.  `npx playwright install chromium` - 安裝 Playwright 的 Chromium 瀏覽器。
4.  `bun scripts/snapshot.js` - 執行快照主腳本。

在首次執行時，它會花一些時間下載所有套件。

## 如何驗證

執行 `snapshot` 腳本是驗證核心環境是否正常的最佳方式。

```bash
bun run snapshot
```

如果這個腳本能成功執行並輸出 `🎉 輕量級快照腳本執行成功！`，就表示：
- Python 環境和依賴已正確安裝。
- `circus` 服務管理器可以正常啟動後端服務。
- Node.js 環境和 `playwright` 依賴已正確安裝。
- Playwright 可以成功擷取快照。

這涵蓋了大部分的開發場景。

## ⚠️ 重要：前端驗證指南 (IMPORTANT: Frontend Verification Guide)

**絕對不要**嘗試透過產生截圖 (`.png`, `.jpg`) 並使用 `read_image_file` 或 `read_file` 工具來進行視覺化驗證。這個方法是**行不通的**。

### 技術限制說明

本專案的執行環境有兩個相互隔離的檔案系統：
1.  **即時執行環境**: `run_in_bash_session` 在此運作，可以產生新檔案。
2.  **唯讀快照環境**: `read_file` 和 `read_image_file` 在此運作，它們只能看到任務開始時的檔案，**無法看到任何在執行期間產生的新檔案**。

這個設計是為了確保執行的穩定性與安全性。任何嘗試在執行期間產生一個檔案然後用讀取工具去存取它的作法，都將會因為 `FileNotFoundError` 而失敗。

### 正確的驗證方法：自動化斷言

所有前端功能的驗證，都**必須**透過在 Playwright 測試腳本中加入**自動化斷言 (Automated Assertions)** 來完成。

與其「看」一個按鈕是否存在，你應該用程式碼去「檢查」它是否存在。

**範例：**

```javascript
// 不好的作法 ❌: 產生截圖讓人類或 AI 去看
await page.screenshot({ path: 'screenshot.png' });

// 好的作法 ✅: 使用 Playwright 的 expect() 函式來直接驗證
import { test, expect } from '@playwright/test';

test('首頁應顯示歡迎標題', async ({ page }) => {
  await page.goto('http://127.0.0.1:42649/');

  // 驗證 <h1> 元素是否可見並且文字正確
  const heading = page.locator('h1');
  await expect(heading).toBeVisible();
  await expect(heading).toHaveText('鳳凰音訊轉錄儀');

  // 驗證「選擇檔案」按鈕是否存在
  const fileInput = page.locator('input[type="file"]');
  await expect(fileInput).toBeEnabled();
});
```

這種方法不僅更可靠、更快速，也完全不受檔案系統的限制。同時，它避免了為執行圖形介面而需要安裝大量系統級依賴套件 (`install-deps`) 的麻煩，讓測試流程更輕量、更穩定。

## 重要文件檢查清單

當除錯啟動問題時，請依序檢查以下文件：
1.  **`package.json`**: 檢查 `scripts` 區塊中的 `snapshot` 指令是否完整。
2.  **`scripts/snapshot.js`**: 這是主要的協調腳本。
3.  **`scripts/run_server_for_playwright.py`**: 這是啟動 Python 伺服器的腳本。
4.  **`config/circus.ini.template`**: 這是 `circus` 服務管理器的設定範本，定義了後端服務如何被啟動。
5.  **`logs/` 目錄下的日誌檔**: 尤其是在 `snapshot` 腳本執行失敗後，`circus.log`, `api_server.err` 等檔案會包含最關鍵的錯誤訊息。
