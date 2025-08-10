import time
import os
import sys
import subprocess
import signal
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Page, TimeoutError as PlaywrightTimeoutError
import re

# --- 設定 ---
# 移除寫死的埠號和 URL
ACTION_TIMEOUT = 20000  # 毫秒
SCREENSHOT_FILE = "test-results/final_verification.png"
DUMMY_FILE_NAME_1 = "dummy_audio_1.wav"
DUMMY_FILE_NAME_2 = "dummy_audio_2.wav"
# 注意：這個模擬腳本文字需要與 mock_transcriber.py 中的輸出完全一致
MOCK_TRANSCRIPT_TEXT = "你好，歡迎使用鳳凰音訊轉錄儀。這是一個模擬的轉錄過程。我們正在逐句產生文字。這個功能將會帶來更好的使用者體驗。轉錄即將完成。"

def create_dummy_wav(filename: str):
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

def cleanup(orchestrator_proc):
    """清理測試產生的檔案和程序。"""
    print("▶️ 執行清理程序...")

    # 1. 終止伺服器程序
    if orchestrator_proc and orchestrator_proc.poll() is None:
        print(f"▶️ 正在終止協調器程序組 (PID: {orchestrator_proc.pid})...")
        try:
            if sys.platform != "win32":
                os.killpg(os.getpgid(orchestrator_proc.pid), signal.SIGTERM)
            else:
                orchestrator_proc.terminate()
            orchestrator_proc.wait(timeout=10)
            print("✅ 協調器已成功終止。")
        except Exception as e:
            print(f"🔥 終止協調器時發生錯誤: {e}", file=sys.stderr)
            if orchestrator_proc.poll() is None:
                orchestrator_proc.kill()

    # 2. 刪除臨時檔案
    files_to_delete = [Path(DUMMY_FILE_NAME_1), Path(DUMMY_FILE_NAME_2)]
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"🗑️ 已刪除檔案: {f.name}")


def run_e2e_test(app_url: str):
    """
    執行完整的端對端驗證。
    """
    # 建立測試所需檔案
    dummy_file_1_path = create_dummy_wav(DUMMY_FILE_NAME_1)
    dummy_file_2_path = create_dummy_wav(DUMMY_FILE_NAME_2)

    # 確保截圖目錄存在
    Path("test-results").mkdir(exist_ok=True)

    page = None # 在 with 區塊外宣告
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(ACTION_TIMEOUT)

            # 監聽並印出瀏覽器主控台的訊息
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

            print(f"▶️ 導航至: {app_url}")
            page.goto(app_url)

            # --- 1. 驗證標題 ---
            print("▶️ 驗證頁面標題...")
            expect(page).to_have_title("音訊轉錄儀")
            expect(page.locator("h1")).to_have_text("音訊轉錄儀")
            print("✅ 頁面標題驗證成功。")

            # --- 2. 驗證檔案上傳與移除功能 ---
            print("▶️ 驗證檔案上傳與移除...")
            page.locator("#file-input").set_input_files([str(dummy_file_1_path), str(dummy_file_2_path)])

            file_list = page.locator("#file-list")
            expect(file_list.locator(".task-item", has_text=DUMMY_FILE_NAME_1)).to_be_visible()
            expect(file_list.locator(".task-item", has_text=DUMMY_FILE_NAME_2)).to_be_visible()
            print("✅ 檔案已成功顯示在待上傳列表。")

            # 移除第二個檔案
            file_item_2 = file_list.locator(".task-item", has_text=DUMMY_FILE_NAME_2)
            file_item_2.locator('button:has-text("移除")').click()

            expect(file_list.locator(".task-item", has_text=DUMMY_FILE_NAME_1)).to_be_visible()
            expect(file_list.locator(".task-item", has_text=DUMMY_FILE_NAME_2)).not_to_be_visible()
            print("✅ 檔案移除功能驗證成功。")

            # --- 3. 驗證進階選項與轉錄流程 ---
            print("▶️ 驗證進階選項與轉錄流程...")
            page.locator("#model-select").select_option("large-v3")
            page.locator("#beam-size-input").fill("3")
            page.locator("#confirm-settings-btn").click()

            progress_container = page.locator("#model-progress-container")
            expect(progress_container).not_to_be_hidden(timeout=5000)
            expect(progress_container.locator("#model-progress-text")).to_contain_text("下載完成")
            print("✅ 模型下載進度條顯示與完成狀態驗證成功。")

            start_btn = page.locator("#start-processing-btn")
            expect(start_btn).to_be_enabled()
            start_btn.click()

            print("▶️ 等待任務出現在「已完成」列表中...")
            completed_tasks_list = page.locator("#completed-tasks")
            task_item = completed_tasks_list.locator(".task-item", has_text=DUMMY_FILE_NAME_1)
            expect(task_item).to_be_visible(timeout=ACTION_TIMEOUT)
            print("✅ 任務已完成並顯示在列表中。")

            # --- 4. 驗證 UI 樣式與佈局 ---
            print("▶️ 驗證已完成任務的按鈕樣式...")
            preview_button = page.locator(f'#completed-tasks .task-item:has-text("{DUMMY_FILE_NAME_1}") a.btn-preview')
            download_button = page.locator(f'#completed-tasks .task-item:has-text("{DUMMY_FILE_NAME_1}") a.btn-download')

            expect(preview_button).to_be_visible()
            preview_color = preview_button.evaluate("element => window.getComputedStyle(element).backgroundColor")
            assert preview_color == "rgb(0, 123, 255)", f"預期預覽按鈕顏色為 rgb(0, 123, 255)，實際為 {preview_color}"

            expect(download_button).to_be_visible()
            download_color = download_button.evaluate("element => window.getComputedStyle(element).backgroundColor")
            assert download_color == "rgb(40, 167, 69)", f"預期下載按鈕顏色為 rgb(40, 167, 69)，實際為 {download_color}"
            print("✅ 按鈕顏色驗證成功。")

            # --- 5. 驗證即時預覽與日誌 ---
            print("▶️ 驗證即時預覽...")
            preview_area = page.locator("#preview-area")
            expect(preview_area).to_be_hidden()
            preview_button.click()
            time.sleep(0.5) # 增加一個小延遲以確保 UI 更新
            expect(preview_area).to_be_visible()
            # 修正：使用正確的 ID 選擇器 #preview-content-text
            expect(preview_area.locator("#preview-content-text")).to_contain_text(MOCK_TRANSCRIPT_TEXT)
            print("✅ 即時預覽功能驗證成功。")

            print("▶️ 驗證轉錄結果反向排序...")
            transcript_output = page.locator("#transcript-output")
            p_elements = transcript_output.locator("p")
            expect(p_elements).to_have_count(6)
            expect(p_elements.first).to_contain_text("轉錄即將完成。")
            print("✅ 轉錄結果反向排序與顯示驗證成功。")

            print("▶️ 驗證日誌查看器...")
            page.locator("#fetch-logs-btn").click()
            expect(page.locator("#log-output")).not_to_contain_text("載入...", timeout=5000)
            expect(page.locator("#log-output")).to_contain_text("[api_server]")
            print("✅ 日誌查看器功能驗證成功。")

            page.screenshot(path=SCREENSHOT_FILE)
            print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")

            browser.close()

    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}", file=sys.stderr)
        if page and not page.is_closed():
            page.screenshot(path="test-results/error_screenshot.png")
            print("📸 已儲存錯誤時的螢幕截圖。")
        # 重新引發異常，以便主執行塊可以捕獲它
        raise

if __name__ == "__main__":
    orchestrator_proc = None
    try:
        # 1. 啟動後端伺服器 (使用 mock 模式)
        print("▶️ 正在啟動後端伺服器 (mock 模式)...")
        cmd = [sys.executable, "orchestrator.py", "--mock"]
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

        orchestrator_proc = subprocess.Popen(cmd, **popen_kwargs)
        print(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        # 2. 等待伺服器就緒並獲取 URL
        app_url = None
        proxy_url_pattern = re.compile(r"PROXY_URL:\s*(http://127\.0\.0\.1:\d+)")
        timeout = time.time() + 45 # 45 秒超時

        for line in iter(orchestrator_proc.stdout.readline, ''):
            print(f"[Orchestrator]: {line.strip()}")
            url_match = proxy_url_pattern.search(line)
            if url_match:
                app_url = url_match.group(1)
                print(f"✅ 偵測到應用程式 URL: {app_url}")
                # 增加一個短暫的延遲，確保服務完全可訪問
                time.sleep(3)
                break
            if time.time() > timeout:
                raise RuntimeError("等待後端伺服器就緒超時。")

        if not app_url:
            raise RuntimeError("未能獲取應用程式 URL。")

        # 3. 執行 E2E 測試
        run_e2e_test(app_url)
        print("\n🎉🎉🎉 端對端自動化驗證成功！ 🎉🎉🎉")

    except Exception as e:
        print(f"\n🔥🔥🔥 端對端自動化驗證失敗: {e} 🔥🔥🔥", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup(orchestrator_proc)
        sys.exit(0)
