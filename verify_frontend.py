# verify_frontend.py (new version)
import time
import os
import subprocess
import signal
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Page, TimeoutError as PlaywrightTimeoutError
import requests
import shutil

# --- 設定 ---
SERVER_URL = "http://127.0.0.1:8000"
APP_URL = f"{SERVER_URL}/"
SERVER_START_TIMEOUT = 30
ACTION_TIMEOUT = 20000  # 毫秒，增加等待時間以應對任務處理
LOG_FILE = Path("run_log.txt")
DB_FILE = Path("db.sqlite3")
TRANSCRIPTS_DIR = Path("transcripts")
UPLOADS_DIR = Path("uploads")
SCREENSHOT_FILE = "frontend_verification.png"
DUMMY_FILE_NAME = "dummy_audio.wav"
MOCK_TRANSCRIPT_TEXT = "這是模擬的轉錄結果。"

def create_dummy_wav(filename=DUMMY_FILE_NAME):
    """建立一個簡短的、無聲的 WAV 檔案用於測試上傳。"""
    import wave
    filepath = Path(filename).resolve()
    with wave.open(str(filepath), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 16000 * 1) # 1 秒的靜音
    print(f"✅ 已建立臨時音訊檔案於: {filepath}")
    return filepath

def cleanup():
    """清理測試產生的檔案和目錄。"""
    print("▶️ 執行清理程序...")
    files_to_delete = [LOG_FILE, DB_FILE, Path(DUMMY_FILE_NAME), Path(SCREENSHOT_FILE)]
    dirs_to_delete = [TRANSCRIPTS_DIR, UPLOADS_DIR]

    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"🗑️ 已刪除檔案: {f.name}")

    for d in dirs_to_delete:
        if d.is_dir():
            shutil.rmtree(d)
            print(f"🗑️ 已刪除目錄: {d.name}")


def run_verification():
    """
    執行完整的端對端驗證，包括啟動後端伺服器和背景工作者。
    """
    server_process = None
    worker_process = None

    # 在開始前先清理一次，確保環境乾淨
    cleanup()

    try:
        print("▶️ 啟動後端伺服器 (模擬模式)...")
        # 統一使用 --mock 旗標，與 orchestrator.py 和 api_server.py 的設計保持一致
        server_command = [sys.executable, "api_server.py", "--port", "8000", "--mock"]
        server_process = subprocess.Popen(server_command, preexec_fn=os.setsid)

        # print("▶️ 啟動背景工作者 (模擬模式)...") # REMOVED: Worker is deprecated.
        # worker_command = [sys.executable, "worker.py", "--mock", "--poll-interval", "1"]
        worker_process = None # subprocess.Popen(worker_command, preexec_fn=os.setsid)

        start_time = time.time()
        server_ready = False
        print(f"⏳ 等待伺服器啟動... (超時: {SERVER_START_TIMEOUT} 秒)")
        while time.time() - start_time < SERVER_START_TIMEOUT:
            try:
                response = requests.get(f"{SERVER_URL}/api/health", timeout=1)
                if response.status_code == 200:
                    print("✅ 伺服器已成功啟動。")
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(0.5)

        if not server_ready:
            raise RuntimeError(f"伺服器在 {SERVER_START_TIMEOUT} 秒內未成功啟動。")

        dummy_file_path = create_dummy_wav()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 監聽並印出瀏覽器主控台的訊息，以便除錯
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

            page.set_default_timeout(ACTION_TIMEOUT)

            print(f"▶️ 導航至: {APP_URL}")
            page.goto(APP_URL)

            print(f"▶️ 模擬操作: 上傳檔案 '{DUMMY_FILE_NAME}'")
            page.locator("#file-input").set_input_files(dummy_file_path)

            print("▶️ 模擬操作: 點擊「開始處理」按鈕")
            expect(page.locator("#start-processing-btn")).to_be_enabled()
            page.locator("#start-processing-btn").click()

            print("▶️ 等待任務出現在「已完成」列表中...")
            # JULES: 加入一個短暫的延遲，以診斷潛在的競爭條件問題
            page.wait_for_timeout(2000)
            completed_tasks_list = page.locator("#completed-tasks")
            task_item = completed_tasks_list.locator(".task-item", has_text=DUMMY_FILE_NAME)

            expect(task_item).to_be_visible(timeout=ACTION_TIMEOUT)
            print("✅ 任務已完成並顯示在列表中。")

            print("▶️ 驗證「預覽」和「下載」按鈕...")
            preview_button = task_item.locator('a:has-text("預覽")')
            download_button = task_item.locator('a:has-text("下載")')

            expect(preview_button).to_be_visible()
            expect(preview_button).to_have_attribute("target", "_blank")
            print("✅ 「預覽」按鈕驗證成功。")

            expect(download_button).to_be_visible()
            expect(download_button).to_have_attribute("download", "dummy_audio_transcript.txt")
            print("✅ 「下載」按鈕驗證成功。")

            print("▶️ 驗證「預覽」功能...")
            with page.expect_popup() as popup_info:
                preview_button.click()

            preview_page = popup_info.value
            preview_page.wait_for_load_state()

            expect(preview_page.locator('body')).to_contain_text(MOCK_TRANSCRIPT_TEXT, timeout=5000)
            print("✅ 「預覽」內容驗證成功。")
            preview_page.close()

            page.screenshot(path=SCREENSHOT_FILE)
            print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")

            browser.close()
            return True

    except Exception as e:
        print(f"❌ 驗證過程中發生錯誤: {e}", file=sys.stderr)
        return False
    finally:
        print("▶️ 執行最終清理...")
        processes = [server_process, worker_process] # worker_process is None, so this is safe
        for proc in processes:
            if proc and proc.poll() is None:
                # 使用 SIGTERM 優雅地終止行程組
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                print(f"✅ 已發送終止信號至行程組 (PID: {proc.pid})。")

        for proc in processes:
            if proc:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    print(f"⚠️ 行程組 (PID: {proc.pid}) 未能終止，已強制終止。", file=sys.stderr)

        cleanup()


if __name__ == "__main__":
    if run_verification():
        print("\n🎉🎉🎉 前端自動化驗證成功！ 🎉🎉🎉")
        sys.exit(0)
    else:
        print("\n🔥🔥🔥 前端自動化驗證失敗。 🔥🔥🔥", file=sys.stderr)
        sys.exit(1)
