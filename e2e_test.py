import sys
import subprocess
import time
import os
import re
import signal
from playwright.sync_api import sync_playwright, expect

# --- 設定 ---
API_KEY = "AIzaSyBdw0gY2oh2W_r1eN3ALzK9RCAAcedgF3E"
YOUTUBE_URL = "https://youtube.com/shorts/huw4_746eG8?si=V_wbOIT_I9QGIv7a"
BILIBILI_URL = "https://b23.tv/3YPqeMs"
SERVER_LAUNCH_COMMAND = [sys.executable, "src/core/orchestrator.py"]
SERVER_READY_TIMEOUT = 120
PROXY_URL_PATTERN = re.compile(r"PROXY_URL: (http://127\.0\.0\.1:\d+)")
UVICORN_READY_PATTERN = re.compile(r"Uvicorn running on")
SUCCESS_SCREENSHOT_FILE = "e2e_test_report.jpg"
ERROR_SCREENSHOT_FILE = "e2e_test_error.jpg"

def main():
    """主函數，執行完整的 E2E 測試流程。"""
    print("--- 啟動 E2E 測試 ---")
    server_process = None

    try:
        # --- 步驟 1: 啟動後端伺服器 ---
        print(f"🚀 正在啟動伺服器: {' '.join(SERVER_LAUNCH_COMMAND)}")
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
        print(f"🕕 正在等待伺服器就緒 (超時: {SERVER_READY_TIMEOUT} 秒)...")
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
                print(f"✅ 伺服器已完全就緒 (Uvicorn is running)!")
                server_truly_ready = True
                break
            if time.time() - start_time > SERVER_READY_TIMEOUT:
                raise TimeoutError("伺服器啟動超時。")

        if not proxy_url or not server_truly_ready:
            raise RuntimeError("無法在超時前啟動伺服器或捕獲到 URL。")

        # --- 步驟 3: 執行 Playwright 測試 (含錯誤截圖修正) ---
        print("\n--- 🤖 啟動 Playwright 瀏覽器測試 ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                print(f"導航至: {proxy_url}")
                page.goto(proxy_url, wait_until="networkidle")

                print("1. 驗證 Whisper 模型預設值...")
                expect(page.locator("#model-select")).to_have_value("tiny")
                print("✅ 預設模型為 'tiny'。")

                print("2. 驗證 Gemini API 金鑰和模型列表...")
                page.locator('button[data-tab="youtube-report-tab"]').click()
                page.locator("#api-key-input").fill(API_KEY)
                page.locator("#save-api-key-btn").click()
                expect(page.locator("#api-key-status")).to_contain_text("金鑰有效", timeout=30000)
                print("✅ API 金鑰驗證成功。")
                gemini_model_select = page.locator("#gemini-model-select")
                expect(gemini_model_select).to_contain_text("Gemini", timeout=20000)
                print("✅ Gemini 模型列表載入成功。")

                print("3. 驗證 YouTube 音訊下載...")
                page.locator(".youtube-url-input").first.fill(YOUTUBE_URL)
                page.locator("#download-audio-only-btn").click()

                ongoing_task_locator_yt = page.locator(f'#ongoing-tasks .task-item:has-text("youtube.com")')
                expect(ongoing_task_locator_yt).to_be_visible(timeout=30000)
                print("   - ✅ 任務已建立。")
                expect(ongoing_task_locator_yt).not_to_be_visible(timeout=300000)
                print("   - ✅ 任務已處理。")

                completed_task_locator_yt = page.locator('#completed-tasks .task-item:has-text("Shape of You")')
                expect(completed_task_locator_yt).to_be_visible(timeout=5000)
                print("✅ YouTube 任務成功出現在已完成列表。")

                preview_button_yt = completed_task_locator_yt.locator('a:has-text("預覽")')
                expect(preview_button_yt).to_be_visible()
                preview_button_yt.click()
                expect(page.locator("#preview-modal")).to_be_visible()
                expect(page.locator("#preview-modal audio")).to_be_visible()
                print("✅ YouTube 任務預覽功能正常。")
                page.locator("#modal-close-btn").click()

                print("4. 驗證 Bilibili 音訊下載...")
                page.locator("#add-youtube-row-btn").click()
                page.locator(".youtube-url-input").last.fill(BILIBILI_URL)
                page.locator("#download-audio-only-btn").click()

                ongoing_task_locator_bili = page.locator(f'#ongoing-tasks .task-item:has-text("b23.tv")')
                expect(ongoing_task_locator_bili).to_be_visible(timeout=30000)
                print("   - ✅ 任務已建立。")
                expect(ongoing_task_locator_bili).not_to_be_visible(timeout=300000)
                print("   - ✅ 任務已處理。")

                completed_task_locator_bili = page.locator('#completed-tasks .task-item:has-text("【年度巨献】环大陆骑行")')
                expect(completed_task_locator_bili).to_be_visible(timeout=5000)
                print("✅ Bilibili 任務成功出現在已完成列表。")

                preview_button_bili = completed_task_locator_bili.locator('a:has-text("預覽")')
                expect(preview_button_bili).to_be_visible()
                print("✅ Bilibili 任務預覽按鈕可見。")

                print(f"📸 正在擷取最終螢幕截圖至 {SUCCESS_SCREENSHOT_FILE}...")
                page.screenshot(path=SUCCESS_SCREENSHOT_FILE, full_page=True)
                print("✅ 截圖成功。")

                print("\n🎉 E2E 測試全部成功！")

            except Exception as e:
                print(f"❌ E2E 測試失敗: {e}")
                print(f"📸 正在擷取錯誤螢幕截圖至 {ERROR_SCREENSHOT_FILE}...")
                page.screenshot(path=ERROR_SCREENSHOT_FILE, full_page=True)
                print("✅ 錯誤截圖成功。")
                raise  # 將異常重新拋出，以使腳本以失敗狀態退出

            finally:
                browser.close()

    finally:
        # --- 步驟 5: 清理環境 ---
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

        # 不再自我刪除，以便審查
        print("測試腳本執行完畢，將予以保留以供審查。")

if __name__ == "__main__":
    main()
