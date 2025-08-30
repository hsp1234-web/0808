import sys
import subprocess
import time
import os
import re
import signal
from playwright.sync_api import sync_playwright, expect

# --- 設定 (使用新的 URL) ---
API_KEY = "AIzaSyBdw0gY2oh2W_r1eN3ALzK9RCAAcedgF3E"
FACEBOOK_URL = "https://www.facebook.com/share/r/15vGn3ZjAg/"
YOUTUBE_URL = "https://youtube.com/shorts/HMS4V6VTIaI?si=UgJD_EiARGXb15VX"
BILIBILI_URL = "https://b23.tv/fIrcbOg"

SERVER_LAUNCH_COMMAND = [sys.executable, "src/core/orchestrator.py"]
SERVER_READY_TIMEOUT = 120
PROXY_URL_PATTERN = re.compile(r"PROXY_URL: (http://127\.0\.0\.1:\d+)")
UVICORN_READY_PATTERN = re.compile(r"Uvicorn running on")
SUCCESS_SCREENSHOT_FILE = "e2e_test_report_new_urls.jpg"
ERROR_SCREENSHOT_FILE = "e2e_test_error_new_urls.jpg"

def main():
    """主函數，使用新的 URL 列表執行 E2E 測試。"""
    print("--- 啟動 E2E 測試 (使用新 URL) ---")
    server_process = None

    try:
        # --- 步驟 1: 啟動後端伺服器 ---
        print(f"🚀 正在啟動伺服器...")
        process_env = os.environ.copy()
        src_path = os.path.abspath("src")
        process_env['PYTHONPATH'] = f"{src_path}{os.pathsep}{process_env.get('PYTHONPATH', '')}"

        server_process = subprocess.Popen(
            SERVER_LAUNCH_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            preexec_fn=os.setsid,
            env=process_env
        )
        print(f"伺服器程序已啟動，PID: {server_process.pid}")

        # --- 步驟 2: 等待伺服器就緒 ---
        print(f"🕕 正在等待伺服器就緒...")
        start_time = time.time()
        proxy_url = None
        server_truly_ready = False
        for line in iter(server_process.stdout.readline, ''):
            print(f"[伺服器日誌] {line.strip()}")
            if not proxy_url:
                url_match = PROXY_URL_PATTERN.search(line)
                if url_match:
                    proxy_url = url_match.group(1)
                    print(f"📝 捕獲到候選 URL: {proxy_url}")
            if UVICORN_READY_PATTERN.search(line):
                print(f"✅ 伺服器已完全就緒!")
                server_truly_ready = True
                break
            if time.time() - start_time > SERVER_READY_TIMEOUT:
                raise TimeoutError("伺服器啟動超時。")

        if not proxy_url or not server_truly_ready:
            raise RuntimeError("無法在超時前啟動伺服器或捕獲到 URL。")

        # --- 步驟 3: 執行 Playwright 測試 ---
        print("\n--- 🤖 啟動 Playwright 瀏覽器測試 ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                print(f"導航至: {proxy_url}")
                page.goto(proxy_url, wait_until="networkidle")

                print("1. 驗證核心功能 (UI 預設值, Gemini 金鑰)...")
                expect(page.locator("#model-select")).to_have_value("tiny")
                page.locator('button[data-tab="youtube-report-tab"]').click()
                page.locator("#api-key-input").fill(API_KEY)
                page.locator("#save-api-key-btn").click()
                expect(page.locator("#api-key-status")).to_contain_text("金鑰有效", timeout=30000)
                expect(page.locator("#gemini-model-select")).to_contain_text("Gemini", timeout=20000)
                print("✅ 核心功能驗證通過。")

                # --- 逐一測試新 URL ---

                # 測試 YouTube
                print("2. 測試 YouTube 下載...")
                page.locator(".youtube-url-input").first.fill(YOUTUBE_URL)
                page.locator("#download-audio-only-btn").click()
                ongoing_yt = page.locator(f'#ongoing-tasks .task-item:has-text("youtube.com")')
                expect(ongoing_yt).to_be_visible(timeout=30000)
                print("   - YouTube 任務已建立。")
                expect(ongoing_yt).not_to_be_visible(timeout=300000)
                print("   - YouTube 任務已處理。")
                completed_yt = page.locator('#completed-tasks .task-item:has-text("The Coconut Song")')
                expect(completed_yt).to_be_visible(timeout=5000)
                print("✅ YouTube 任務成功！")

                # 測試 Bilibili
                print("3. 測試 Bilibili 下載...")
                page.locator("#add-youtube-row-btn").click()
                page.locator(".youtube-url-input").last.fill(BILIBILI_URL)
                page.locator("#download-audio-only-btn").click()
                ongoing_bili = page.locator(f'#ongoing-tasks .task-item:has-text("b23.tv")')
                expect(ongoing_bili).to_be_visible(timeout=30000)
                print("   - Bilibili 任務已建立。")
                expect(ongoing_bili).not_to_be_visible(timeout=300000)
                print("   - Bilibili 任務已處理。")
                completed_bili = page.locator('#completed-tasks .task-item:has-text("【没丸没了】5分钟速通版")')
                expect(completed_bili).to_be_visible(timeout=5000)
                print("✅ Bilibili 任務成功！")

                # 測試 Facebook
                print("4. 測試 Facebook 下載...")
                page.locator("#add-youtube-row-btn").click()
                page.locator(".youtube-url-input").last.fill(FACEBOOK_URL)
                page.locator("#download-audio-only-btn").click()
                ongoing_fb = page.locator(f'#ongoing-tasks .task-item:has-text("facebook.com")')
                expect(ongoing_fb).to_be_visible(timeout=30000)
                print("   - Facebook 任務已建立。")
                expect(ongoing_fb).not_to_be_visible(timeout=300000)
                print("   - Facebook 任務已處理。")
                # Facebook titles can be generic, so we'll just check for completion
                completed_fb = page.locator(f'#completed-tasks .task-item:has-text("www.facebook.com")')
                expect(completed_fb).to_be_visible(timeout=5000)
                print("✅ Facebook 任務成功！")


                print(f"📸 正在擷取最終螢幕截圖至 {SUCCESS_SCREENSHOT_FILE}...")
                page.screenshot(path=SUCCESS_SCREENSHOT_FILE, full_page=True)
                print("✅ 截圖成功。")

                print("\n🎉 E2E 測試全部成功！")

            except Exception as e:
                print(f"❌ E2E 測試失敗: {e}")
                print(f"📸 正在擷取錯誤螢幕截圖至 {ERROR_SCREENSHOT_FILE}...")
                page.screenshot(path=ERROR_SCREENSHOT_FILE, full_page=True)
                print("✅ 錯誤截圖成功。")
                raise

            finally:
                browser.close()

    finally:
        if server_process and server_process.poll() is None:
            print("\n🧹 正在終止伺服器進程...")
            try:
                os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                server_process.wait(timeout=10)
                print("伺服器已終止。")
            except ProcessLookupError:
                print("伺服器程序已自行終止。")
            except Exception as kill_e:
                print(f"終止伺服器時發生錯誤: {kill_e}")

        print("測試腳本執行完畢，將予以保留以供審查。")

if __name__ == "__main__":
    main()
