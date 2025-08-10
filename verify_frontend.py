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
MOCK_TRANSCRIPT_TEXT = "你好，歡迎使用鳳凰音訊轉錄儀。這是一個模擬的轉錄過程。我們正在逐句產生文字。這個功能將會帶來更好的使用者體驗。轉錄即將完成。"

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
    # JULES: 根據需求，保留螢幕截圖檔案以供檢視，不再於清理過程中自動刪除。
    files_to_delete = [LOG_FILE, DB_FILE, Path(DUMMY_FILE_NAME)] #, Path(SCREENSHOT_FILE)]
    dirs_to_delete = [TRANSCRIPTS_DIR, UPLOADS_DIR]

    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"🗑️ 已刪除檔案: {f.name}")

    for d in dirs_to_delete:
        if d.is_dir():
            shutil.rmtree(d)
            print(f"🗑️ 已刪除目錄: {d.name}")


def test_local_file_upload(page: Page):
    """測試本地檔案上傳、處理和預覽功能。"""
    print("\n▶️ --- 開始本地檔案上傳功能驗證 ---")

    page.goto(APP_URL)
    page.locator('button[data-tab="local-file-tab"]').click()

    dummy_file_path = create_dummy_wav()
    page.locator("#file-input").set_input_files(dummy_file_path)
    print("✅ 已選擇用於上傳的檔案。")

    expect(page.locator("#start-processing-btn")).to_be_enabled()
    page.locator("#start-processing-btn").click()
    print("✅ 已點擊開始處理按鈕。")

    completed_tasks_list = page.locator("#completed-tasks")
    task_item = completed_tasks_list.locator(".task-item", has_text=DUMMY_FILE_NAME)
    expect(task_item).to_be_visible(timeout=ACTION_TIMEOUT)
    print("✅ 任務已出現在「已完成」列表中。")

    preview_button = task_item.locator('a:has-text("預覽")')
    expect(preview_button).to_be_visible()

    print("▶️ 驗證「預覽」功能...")
    preview_area = page.locator("#preview-area")
    expect(preview_area).to_be_hidden()
    preview_button.click()
    expect(preview_area).to_be_visible(timeout=5000)
    expect(preview_area.locator("#preview-content-text")).to_contain_text(MOCK_TRANSCRIPT_TEXT, timeout=5000)
    print("✅ 「預覽」文字內容驗證成功。")

    page.locator("#close-preview-btn").click()
    expect(preview_area).to_be_hidden()
    print("✅ 「關閉預覽」功能驗證成功。")
    print("🎉 --- 本地檔案上傳功能驗證成功 ---")

def test_youtube_feature(page: Page):
    """測試 YouTube 處理功能。"""
    print("\n▶️ --- 開始 YouTube 功能驗證 ---")

    page.goto(APP_URL)
    page.locator('button[data-tab="youtube-tab"]').click()
    youtube_tab = page.locator("#youtube-tab")
    expect(youtube_tab).to_be_visible()
    print("✅ 已成功切換到 YouTube 功能分頁。")

    expect(page.locator("#api-key-success")).to_be_visible(timeout=10000)
    expect(page.locator("#youtube-controls-fieldset")).to_be_enabled(timeout=10000)
    gemini_model_select = page.locator("#gemini-model-select")
    expect(gemini_model_select.locator("option")).to_have_count(2, timeout=10000)
    print("✅ API 金鑰已啟用，Gemini 模型列表載入成功。")

    youtube_urls_input = page.locator("#youtube-urls-input")
    start_youtube_btn = page.locator("#start-youtube-processing-btn")

    mock_youtube_url = "https://www.youtube.com/watch?v=mock_video_id"
    youtube_urls_input.fill(mock_youtube_url)
    expect(start_youtube_btn).to_be_enabled()
    start_youtube_btn.click()
    print(f"✅ 已輸入網址並點擊開始處理按鈕。")

    completed_tasks_list = page.locator("#completed-tasks")
    task_item = completed_tasks_list.locator(".task-item", has_text=mock_youtube_url)
    expect(task_item).to_be_visible(timeout=ACTION_TIMEOUT * 2) # YouTube 處理可能更久
    print("✅ YouTube 任務已出現在「已完成」列表中。")

    preview_button = task_item.locator('a:has-text("預覽")')
    expect(preview_button).to_be_visible()

    print("▶️ 驗證 YouTube 報告的「預覽」功能 (PDF)...")

    # JULES: 為避免瀏覽器在自動化測試中攔截彈出視窗，
    # 我們不直接點擊，而是獲取其 href 屬性並直接用 requests 驗證。
    pdf_url_path = preview_button.get_attribute("href")
    assert pdf_url_path, "預覽按鈕應有 href 屬性"

    full_pdf_url = f"{SERVER_URL}{pdf_url_path}"
    print(f"✅ 預覽按鈕指向正確的 URL: {full_pdf_url}")

    # 直接請求該 URL 並驗證內容
    print("✅ 正在直接請求 URL 以驗證 PDF 內容...")
    pdf_response = requests.get(full_pdf_url)
    assert pdf_response.status_code == 200, f"請求 PDF 應回傳 200 OK，但得到 {pdf_response.status_code}"
    assert 'application/pdf' in pdf_response.headers.get('Content-Type', ''), "回應的 Content-Type 應為 application/pdf"
    assert pdf_response.content.startswith(b'%PDF-'), "回應內容應為 PDF 檔案"

    print("✅ 已成功驗證後端回傳了正確的 PDF 檔案。")

    print("🎉 --- YouTube 功能驗證成功 ---")

if __name__ == "__main__":
    cleanup()
    db_manager_process = None
    server_process = None

    try:
        print("▶️ 啟動資料庫管理器...")
        db_manager_command = [sys.executable, "db/manager.py"]
        db_manager_process = subprocess.Popen(db_manager_command, preexec_fn=os.setsid if sys.platform != "win32" else None)
        time.sleep(2)

        print("▶️ 啟動後端伺服器 (模擬模式)...")
        server_command = [sys.executable, "api_server.py", "--port", "8000", "--mock"]
        server_process = subprocess.Popen(server_command, preexec_fn=os.setsid if sys.platform != "win32" else None)

        start_time = time.time()
        server_ready = False
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
            raise RuntimeError("伺服器未能及時就緒。")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(ACTION_TIMEOUT)
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

            test_local_file_upload(page)
            test_youtube_feature(page)

            page.screenshot(path=SCREENSHOT_FILE)
            print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")
            browser.close()

        print("\n🎉🎉🎉 所有功能自動化驗證成功！ 🎉🎉🎉")
        sys.exit(0)

    except Exception as e:
        print(f"\n🔥🔥🔥 自動化驗證失敗: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("▶️ 執行最終清理...")
        processes = [db_manager_process, server_process]
        for proc in processes:
            if proc and proc.poll() is None:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.terminate()
        cleanup()
