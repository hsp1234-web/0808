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

## 重要文件檢查清單

當除錯啟動問題時，請依序檢查以下文件：
1.  **`package.json`**: 檢查 `scripts` 區塊中的 `snapshot` 指令是否完整。
2.  **`scripts/snapshot.js`**: 這是主要的協調腳本。
3.  **`scripts/run_server_for_playwright.py`**: 這是啟動 Python 伺服器的腳本。
4.  **`config/circus.ini.template`**: 這是 `circus` 服務管理器的設定範本，定義了後端服務如何被啟動。
5.  **`logs/` 目錄下的日誌檔**: 尤其是在 `snapshot` 腳本執行失敗後，`circus.log`, `api_server.err` 等檔案會包含最關鍵的錯誤訊息。
