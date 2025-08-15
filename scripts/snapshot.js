import { spawn } from 'child_process';
import { chromium } from 'playwright';
import path from 'path';

const SCRIPT_TIMEOUT = 60000; // 增加總超時時間以應對可能的 Playwright 首次啟動延遲
const SERVER_LOG_TIMEOUT = 20000; // 同樣增加看門狗超時

async function takeSnapshot() {
    let serverProcess;
    let browser;
    let watchdogTimer;

    const scriptTimeout = setTimeout(() => {
        console.error(`❌ 整個快照腳本執行超時 (${SCRIPT_TIMEOUT / 1000} 秒)。正在強制終止...`);
        if (serverProcess) {
            serverProcess.kill('SIGKILL');
        }
        process.exit(1);
    }, SCRIPT_TIMEOUT);

    try {
        console.log('--- 啟動輕量級快照程序 ---');

        console.log('🐍 正在啟動後端伺服器...');
        const serverScriptPath = path.resolve('scripts', 'run_server_for_playwright.py');
        serverProcess = spawn('python3', [serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe'],
            cwd: process.cwd()
        });

        const resetWatchdog = () => {
            clearTimeout(watchdogTimer);
            watchdogTimer = setTimeout(() => {
                console.error(`❌ 看門狗觸發：伺服器在 ${SERVER_LOG_TIMEOUT / 1000} 秒內無任何日誌輸出。正在終止...`);
                serverProcess.kill('SIGKILL');
            }, SERVER_LOG_TIMEOUT);
        };

        resetWatchdog();

        console.log('[DEBUG] 準備等待伺服器就緒...');
        let serverOutput = '';
        await new Promise((resolve, reject) => {
            serverProcess.stdout.on('data', (data) => {
                const chunk = data.toString();
                serverOutput += chunk;
                console.log(`[伺服器日誌]: ${chunk.trim()}`);
                resetWatchdog();
                if (serverOutput.includes('✅✅✅')) {
                    console.log('[DEBUG] 偵測到伺服器就緒訊息！準備解析 Promise...');
                    resolve();
                }
            });

            serverProcess.stderr.on('data', (data) => {
                const errorOutput = data.toString();
                console.error(`[伺服器錯誤日誌]: ${errorOutput.trim()}`);
                resetWatchdog();
            });

            serverProcess.on('close', (code) => {
                if (code !== 0 && code !== null) {
                    const message = `伺服器意外終止，退出碼: ${code}。`;
                    console.error(`❌ ${message}`);
                    reject(new Error(message));
                }
            });

            serverProcess.on('error', (err) => {
                 console.error('❌ 無法啟動伺服器進程:', err);
                 reject(err);
            });
        });
        console.log('[DEBUG] 伺服器就緒 Promise 已解析。');

        console.log('[DEBUG] 準備啟動 Playwright...');
        browser = await chromium.launch({ headless: true });
        console.log('[DEBUG] Playwright 已啟動。');

        console.log('[DEBUG] 準備開啟新頁面...');
        const page = await browser.newPage();
        console.log('[DEBUG] 新頁面已開啟。');

        console.log('[DEBUG] 準備導航至 URL...');
        await page.goto('http://127.0.0.1:42649/');
        console.log('[DEBUG] 已導航至 URL。');

        console.log('[DEBUG] 準備等待 h1 元素...');
        await page.locator('h1').waitFor({ state: 'visible', timeout: 10000 });
        console.log('[DEBUG] h1 元素已可見。');

        const snapshotPath = 'homepage_snapshot_light.png';
        console.log(`[DEBUG] 準備擷取快照至 ${snapshotPath}...`);
        await page.screenshot({ path: snapshotPath });
        console.log(`✅ 快照成功儲存至: ${snapshotPath}`);

    } catch (error) {
        console.error('💥 在快照過程中發生錯誤:', error);
        throw error;
    } finally {
        console.log('--- 正在關閉所有資源 ---');
        clearTimeout(scriptTimeout);
        clearTimeout(watchdogTimer);

        if (browser) {
            await browser.close();
            console.log('✅ Playwright 瀏覽器已關閉。');
        }

        if (serverProcess && !serverProcess.killed) {
            console.log('优雅地關閉伺服器...');
            serverProcess.kill('SIGTERM');
            console.log('✅ 關閉信號已發送至伺服器。');
        }
    }
}

takeSnapshot().then(() => {
    console.log('\n🎉 輕量級快照腳本執行成功！');
    process.exit(0);
}).catch((err) => {
    console.error('\n🔥 輕量級快照腳本執行失敗。');
    process.exit(1);
});
