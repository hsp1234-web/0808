import time
import os
import sys
import subprocess
import signal
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
import re

# --- 設定 ---
SCREENSHOT_FILE = "final_real_mode_screenshot.png"
SERVER_READY_TIMEOUT = 60 # seconds

def cleanup(proc):
    """清理伺服器程序。"""
    print("▶️  執行清理程序...")
    if proc and proc.poll() is None:
        print(f"▶️  正在終止伺服器程序組 (PID: {proc.pid})...")
        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=10)
            print("✅ 伺服器已成功終止。")
        except Exception as e:
            print(f"🔥 終止伺服器時發生錯誤: {e}", file=sys.stderr)
            if proc.poll() is None:
                proc.kill()

def run_verification(app_url: str):
    """
    啟動瀏覽器，導覽至頁面，並拍攝截圖。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(20000) # 20 秒

        # --- JULES' MODIFICATION: Add retry logic for navigation ---
        max_retries = 5
        for i in range(max_retries):
            try:
                print(f"▶️  導覽至: {app_url} (嘗試 {i+1}/{max_retries})")
                page.goto(app_url, timeout=10000) # 10 second timeout for goto
                print("✅ 頁面導覽成功。")
                break # Success, exit loop
            except Exception as e:
                print(f"🔥 導覽失敗: {e}")
                if i < max_retries - 1:
                    print("... 2秒後重試 ...")
                    time.sleep(2)
                else:
                    print("❌ 已達最大重試次數，測試失敗。")
                    raise # Re-raise the last exception
        # --- END MODIFICATION ---

        # 等待儀表板可見並已填入數據
        print("▶️  等待儀表板元件載入...")
        expect(page.locator("#cpu-label")).not_to_contain_text("--%", timeout=15000)
        expect(page.locator("#ram-label")).not_to_contain_text("--%", timeout=15000)
        print("✅ CPU/RAM 儀表板已更新。")

        # 切換到 YouTube 分頁以顯示 API 金鑰訊息
        print("▶️  切換至 YouTube 分頁...")
        page.locator('button[data-tab="youtube-tab"]').click()

        # 等待 API 金鑰提示可見
        expect(page.locator("#api-key-prompt")).to_be_visible(timeout=10000)
        print("✅ API 金鑰提示已顯示。")

        # 驗證時間戳記開關是否存在
        print("▶️  驗證時間戳記開關存在...")
        expect(page.locator("#timestamp-toggle")).to_be_visible()
        print("✅ 時間戳記開關已找到。")

        print(f"▶️  正在截取最終畫面至 {SCREENSHOT_FILE}...")
        page.screenshot(path=SCREENSHOT_FILE, full_page=True)
        print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")

        browser.close()

def main():
    """主執行函式。"""
    orchestrator_proc = None
    try:
        # 確保 config.json 使用預設值，以觸發警告訊息
        config_content = '{"GOOGLE_API_KEY": "在此處填入您的 GOOGLE API 金鑰"}'
        Path("config.json").write_text(config_content, encoding='utf-8')
        print("✅ 已確認 config.json 使用預設值以觸發提示。")

        # 1. 啟動後端伺服器 (真實模式)
        print("▶️  正在啟動後端伺服器 (真實模式)...")
        cmd = [sys.executable, "orchestrator.py", "--no-mock"]

        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": 'utf-8',
        }
        if sys.platform != "win32":
            popen_kwargs['preexec_fn'] = os.setsid
        else:
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        # 傳遞環境變數，但確保此腳本的 GOOGLE_API_KEY 不會被傳遞
        proc_env = os.environ.copy()
        if "GOOGLE_API_KEY" in proc_env:
            del proc_env["GOOGLE_API_KEY"]
        popen_kwargs["env"] = proc_env

        orchestrator_proc = subprocess.Popen(cmd, **popen_kwargs)
        print(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        # 2. 等待伺服器就緒並取得 URL
        app_url = None
        proxy_url_pattern = re.compile(r"PROXY_URL:\s*(http://127\.0\.0\.1:\d+)")
        timeout = time.time() + SERVER_READY_TIMEOUT

        print(f"▶️  等待伺服器就緒 (最多 {SERVER_READY_TIMEOUT} 秒)...")
        for line in iter(orchestrator_proc.stdout.readline, ''):
            print(f"[Orchestrator]: {line.strip()}")
            url_match = proxy_url_pattern.search(line)
            if url_match:
                app_url = url_match.group(1)
                print(f"✅ 偵測到應用程式 URL: {app_url}")
                time.sleep(5) # 等待伺服器完全可訪問
                break
            if time.time() > timeout:
                raise RuntimeError("等待後端伺服器就緒超時。")

        if not app_url:
            raise RuntimeError("未能獲取應用程式 URL。")

        # 3. 執行 Playwright 驗證
        run_verification(app_url)
        print("\n🎉🎉🎉 UI 驗證與截圖成功！ 🎉🎉🎉")

    except Exception as e:
        print(f"\n🔥🔥🔥 UI 驗證失敗: {e} 🔥🔥🔥", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup(orchestrator_proc)

if __name__ == "__main__":
    main()
