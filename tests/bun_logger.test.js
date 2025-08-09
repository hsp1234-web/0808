import { test, expect, describe, beforeAll, afterAll } from "bun:test";
import { JSDOM } from "jsdom";
import { spawn, execSync } from "node:child_process";
import { readFileSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";

const API_SERVER_URL = "http://127.0.0.1:8000";
const LOG_FILE = path.join(import.meta.dir, '../run_log.txt');

// 輔助函式：等待伺服器啟動
function waitForServer(url, timeout = 20000) {
    const start = Date.now();
    return new Promise((resolve, reject) => {
        const checkServer = async () => {
            try {
                // 我們預期 /api/system_stats 會在伺服器就緒時回傳 200
                const response = await fetch(`${url}/api/system_stats`);
                if (response.ok) {
                    console.log("✅ 伺服器已成功啟動。");
                    resolve();
                } else {
                    // 如果伺服器正在啟動但尚未就緒，可能會回傳非 200 狀態碼
                    throw new Error(`伺服器回應狀態碼: ${response.status}`);
                }
            } catch (error) {
                if (Date.now() - start > timeout) {
                    reject(new Error(`❌ 伺服器在 ${timeout}ms 內沒有回應。`));
                } else {
                    // 稍後重試
                    setTimeout(checkServer, 500);
                }
            }
        };
        checkServer();
    });
}

// 測試套件
describe("Bun Logger Test for demo.html", () => {
    let serverProcess;
    let window;
    let document;

    // 在所有測試開始前，啟動伺服器並設定 JSDOM
    beforeAll(async () => {
        // 強制清除可能殘留在 8000 埠的任何進程，確保測試環境乾淨
        try {
            console.log("▶️ 確保 8000 埠已釋放 (使用 lsof)...");
            // 使用 lsof 和 kill 指令來找到並終止任何正在使用 8000 埠的進程
            execSync("lsof -t -i:8000 | xargs -r kill -9");
            console.log("✅ 8000 埠已成功釋放。");
        } catch (e) {
            // 如果沒有進程佔用該埠，lsof 會回傳非 0 狀態碼，這是正常現象
            console.log("ℹ️ 8000 埠原本就是空閒的。");
        }

        // 啟動後端伺服器
        console.log("▶️ 啟動後端伺服器 (python -m uvicorn)...");
        serverProcess = spawn("python", ["-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", "8000"], {
            detached: true,
        });

        // 監聽伺服器輸出，方便偵錯
        serverProcess.stdout.on('data', (data) => console.log(`[SERVER STDOUT]: ${data}`));
        serverProcess.stderr.on('data', (data) => console.error(`[SERVER STDERR]: ${data}`));

        // 等待伺服器啟動
        await waitForServer(API_SERVER_URL);

        // 讀取 HTML 檔案並設定 JSDOM
        const htmlPath = path.join(import.meta.dir, '../demo.html');
        const htmlContent = readFileSync(htmlPath, 'utf-8');
        const dom = new JSDOM(htmlContent, {
            runScripts: "dangerously",
            url: API_SERVER_URL, // 確保 fetch 的相對路徑正確
        });

        window = dom.window;
        document = dom.window.document;

        // JSDOM 本身不包含 fetch，我們需要手動將 Bun 的 fetch 注入，讓 script 內部可以呼叫
        window.fetch = fetch;

        // 等待 JSDOM 中的 script 執行完成
        await new Promise(resolve => {
             if (document.readyState === "complete") {
                resolve();
            } else {
                window.addEventListener("load", resolve, { once: true });
            }
        });
    });

    // 在所有測試結束後，關閉伺服器
    afterAll(() => {
        if (serverProcess) {
            console.log("▶️ 正在關閉後端伺服器...");
            try {
                // 使用 process.kill 並傳入負的 PID 來殺死整個進程組
                process.kill(-serverProcess.pid);
                console.log("✅ 伺服器已關閉。");
            } catch (e) {
                console.error("關閉伺服器失敗:", e.message);
            }
        }
    });

    // 測試點擊按鈕是否能成功觸發日誌寫入
    test("should write a log to run_log.txt when confirm button is clicked", async () => {
        // 清空日誌檔案以確保測試環境乾淨
        writeFileSync(LOG_FILE, '', 'utf-8');

        const initialStats = statSync(LOG_FILE);
        const initialSize = initialStats.size;

        // JSDOM 不包含 alert, 需要手動模擬
        window.alert = () => {};

        // 找到設定按鈕並點擊
        const confirmBtn = document.getElementById('confirm-settings-btn');
        expect(confirmBtn).not.toBeNull();
        confirmBtn.click();

        // 等待 fetch 請求完成和檔案寫入
        await new Promise(resolve => setTimeout(resolve, 1000));

        const finalStats = statSync(LOG_FILE);
        const finalSize = finalStats.size;

        // 驗證檔案大小是否增加
        expect(finalSize).toBeGreaterThan(initialSize);

        // 驗證檔案內容是否包含預期的日誌訊息
        const logContent = readFileSync(LOG_FILE, 'utf-8');
        expect(logContent).toInclude('"action": "確認設定按鈕點擊"');
        expect(logContent).toInclude('"model": "medium"'); // "medium" 是預設選項
    });
});
