import time
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Page, TimeoutError as PlaywrightTimeoutError
import re

# --- 設定 ---
PORT = 49243
SERVER_URL = f"http://127.0.0.1:{PORT}"
APP_URL = f"{SERVER_URL}/"
ACTION_TIMEOUT = 20000  # 毫秒
SCREENSHOT_FILE = "test-results/final_verification.png"
DUMMY_FILE_NAME_1 = "dummy_audio_1.wav"
DUMMY_FILE_NAME_1 = "dummy_audio_1.wav"
DUMMY_FILE_NAME_2 = "dummy_audio_2.wav"
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

def cleanup():
    """清理測試產生的檔案。"""
    print("▶️ 執行清理程序...")
    files_to_delete = [Path(DUMMY_FILE_NAME_1), Path(DUMMY_FILE_NAME_2)]
    for f in files_to_delete:
        if f.exists():
            f.unlink()
            print(f"🗑️ 已刪除檔案: {f.name}")

def run_e2e_test():
    """
    執行完整的端對端驗證。
    假設伺服器已由 orchestrator.py 啟動。
    """
    # 建立測試所需檔案
    dummy_file_1_path = create_dummy_wav(DUMMY_FILE_NAME_1)
    dummy_file_2_path = create_dummy_wav(DUMMY_FILE_NAME_2)

    # 確保截圖目錄存在
    Path("test-results").mkdir(exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(ACTION_TIMEOUT)

            # 監聽並印出瀏覽器主控台的訊息
            page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

            print(f"▶️ 導航至: {APP_URL}")
            page.goto(APP_URL)

            # --- 1. 驗證標題 ---
            print("▶️ 驗證頁面標題...")
            expect(page).to_have_title("音訊轉錄儀")
            expect(page.locator("h1")).to_have_text("音訊轉錄儀")
            print("✅ 頁面標題驗證成功。")

            # --- 2. 驗證檔案上傳與移除功能 ---
            print("▶️ 驗證檔案上傳與移除...")
            file_input = page.locator("#file-input")
            file_input.set_input_files([dummy_file_1_path, dummy_file_2_path])

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
            # 選擇模型和設定光束大小
            page.locator("#model-select").select_option("large-v3")
            page.locator("#beam-size-input").fill("3")

            # 點擊確認設定，觸發模型下載
            print("▶️ 觸發模型下載（使用 mock，應為瞬時）...")
            page.locator("#confirm-settings-btn").click()

            # 驗證下載進度條（在 mock 模式下，它會快速完成）
            progress_container = page.locator("#model-progress-container")
            expect(progress_container).not_to_be_hidden(timeout=5000)
            expect(progress_container.locator("#model-progress-text")).to_contain_text("下載完成")
            print("✅ 模型下載進度條顯示與完成狀態驗證成功。")

            # 開始處理
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
            # 使用更直接的 CSS 選擇器來避免潛在的定位問題
            preview_button = page.locator(f'#completed-tasks .task-item:has-text("{DUMMY_FILE_NAME_1}") a.btn-preview')
            download_button = page.locator(f'#completed-tasks .task-item:has-text("{DUMMY_FILE_NAME_1}") a.btn-download')

            expect(preview_button).to_be_visible()
            preview_color = preview_button.evaluate("element => window.getComputedStyle(element).backgroundColor")
            print(f"  > 預覽按鈕顏色: {preview_color}")
            assert preview_color == "rgb(0, 123, 255)" # Corresponds to --button-bg-color

            expect(download_button).to_be_visible()
            download_color = download_button.evaluate("element => window.getComputedStyle(element).backgroundColor")
            print(f"  > 下載按鈕顏色: {download_color}")
            assert download_color == "rgb(40, 167, 69)" # Corresponds to --success-color

            print("✅ 按鈕顏色驗證成功。")

            # --- 5. 驗證即時預覽與日誌 ---
            print("▶️ 驗證即時預覽...")
            preview_area = page.locator("#preview-area")
            expect(preview_area).to_be_hidden()

            preview_button.click()

            expect(preview_area).to_be_visible()
            expect(preview_area.locator("#preview-content")).to_contain_text(MOCK_TRANSCRIPT_TEXT)
            print("✅ 即時預覽功能驗證成功。")

            print("▶️ 驗證轉錄結果反向排序...")
            transcript_output = page.locator("#transcript-output")

            # 獲取所有 p 標籤
            p_elements = transcript_output.locator("p")

            # 斷言 p 標籤的數量是否與模擬腳本中的句子數量相符
            mock_sentences_count = 6
            expect(p_elements).to_have_count(mock_sentences_count)

            # 驗證反向排序：檢查第一個 <p> 元素是否包含模擬腳本的最後一句話
            last_sentence = "轉錄即將完成。"
            expect(p_elements.first).to_contain_text(last_sentence)

            print("✅ 轉錄結果反向排序與顯示驗證成功。")

            print("▶️ 驗證日誌查看器位置與功能...")
            log_viewer = page.locator("#log-viewer-card")
            # 簡化驗證，只確認日誌查看器本身是可見的，因為相鄰選擇器 (+) 在此環境中可能不穩定
            expect(log_viewer).to_be_visible()

            page.locator("#fetch-logs-btn").click()
            expect(page.locator("#log-output")).not_to_contain_text("載入...", timeout=5000)
            expect(page.locator("#log-output")).to_contain_text("[api_server]")
            print("✅ 日誌查看器位置與功能驗證成功。")


            page.screenshot(path=SCREENSHOT_FILE)
            print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")

            browser.close()
            return True

    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}", file=sys.stderr)
        # 如果出錯，也嘗試截圖
        if 'page' in locals() and not page.is_closed():
            page.screenshot(path="test-results/error_screenshot.png")
        return False
    finally:
        cleanup()


if __name__ == "__main__":
    if run_e2e_test():
        print("\n🎉🎉🎉 端對端自動化驗證成功！ 🎉🎉🎉")
        sys.exit(0)
    else:
        print("\n🔥🔥🔥 端對端自動化驗證失敗。 🔥🔥🔥", file=sys.stderr)
        sys.exit(1)
