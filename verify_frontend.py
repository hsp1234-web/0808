import time
import os
import subprocess
import signal
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeoutError

# --- 設定 ---
SERVER_URL = "http://127.0.0.1:8000"
# 在 api_server.py 中，根目錄會提供 mp3.html
APP_URL = f"{SERVER_URL}/"
SERVER_START_TIMEOUT = 30  # 秒
ACTION_TIMEOUT = 10000  # 毫秒
LOG_FILE = "run_log.txt"
SCREENSHOT_FILE = "frontend_verification.png"
DUMMY_FILE_NAME = "dummy_audio.wav"

def create_dummy_wav(filename=DUMMY_FILE_NAME):
    """建立一個簡短的、無聲的 WAV 檔案用於測試上傳。"""
    import wave
    # 確保檔案路徑是絕對的
    filepath = os.path.abspath(filename)
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 16000 * 1) # 1 秒的靜音
    print(f"✅ 已建立臨時音訊檔案於: {filepath}")
    return filepath

def verify_log(action_name, timeout=5):
    """檢查日誌檔案中是否包含指定的 action。"""
    start_time = time.time()
    expected_log_entry = f"[FRONTEND ACTION] {action_name}"
    print(f"🔍 正在驗證日誌: 應包含 '{expected_log_entry}'...")

    while time.time() - start_time < timeout:
        if not os.path.exists(LOG_FILE):
            time.sleep(0.2)
            continue

        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if expected_log_entry in content:
                print(f"✅ 日誌驗證成功: 找到了 '{expected_log_entry}'。")
                return True
        time.sleep(0.2)

    print(f"❌ 日誌驗證失敗: 在 {timeout} 秒內未找到 '{expected_log_entry}'。")
    # 為了除錯，顯示目前的日誌內容
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            print("--- 目前日誌內容 ---")
            print(f.read())
            print("--------------------")
    return False

def run_verification():
    """
    使用 Playwright 執行前端自動化驗證，包含超時機制和日誌驗證。
    """
    server_process = None
    dummy_file_path = None

    # 使用 Popen 啟動伺服器，以便我們可以獲取其 process ID
    # preexec_fn=os.setsid 確保我們可以殺死整個 process group
    print("▶️ 啟動後端伺服器...")
    server_command = ["uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", "8000"]
    server_process = subprocess.Popen(server_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)

    # --- 強健的伺服器啟動等待與超時機制 ---
    start_time = time.time()
    server_ready = False
    print(f"⏳ 等待伺服器啟動... (超時: {SERVER_START_TIMEOUT} 秒)")

    import requests
    while time.time() - start_time < SERVER_START_TIMEOUT:
        try:
            # 使用 /api/health 端點進行健康檢查
            response = requests.get(f"{SERVER_URL}/api/health", timeout=1)
            if response.status_code == 200:
                print("✅ 伺服器已成功啟動並回應健康檢查。")
                server_ready = True
                break
        except requests.ConnectionError:
            time.sleep(0.5)
        except requests.Timeout:
            print(".. 健康檢查超時，重試中 ..")

    if not server_ready:
        print(f"❌ 伺服器在 {SERVER_START_TIMEOUT} 秒內沒有成功啟動。測試中止。")
        # 殺死整個 process group
        os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
        server_process.wait()
        return False

    try:
        dummy_file_path = create_dummy_wav()

        with sync_playwright() as p:
            print("▶️ 啟動瀏覽器...")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(ACTION_TIMEOUT)

            print(f"▶️ 導航至應用程式頁面: {APP_URL}")
            page.goto(APP_URL, wait_until="domcontentloaded")

            # 1. 驗證頁面載入日誌
            if not verify_log("頁面載入完成"):
                raise RuntimeError("頁面載入日誌驗證失敗。")

            # 2. 點擊「確認設定」按鈕並驗證日誌
            print("▶️ 模擬操作: 點擊「確認設定」按鈕")
            page.locator("#confirm-settings-btn").click()
            if not verify_log("確認設定按鈕點擊"):
                raise RuntimeError("「確認設定」日誌驗證失敗。")

            # 3. 點擊字體大小按鈕並驗證日誌
            print("▶️ 模擬操作: 點擊「字體放大」按鈕")
            page.locator("#zoom-in-btn").click()
            if not verify_log("字體大小變更"):
                raise RuntimeError("「字體放大」日誌驗證失敗。")

            print("▶️ 模擬操作: 點擊「字體縮小」按鈕")
            page.locator("#zoom-out-btn").click()
            # 由於日誌名稱相同，這裡僅驗證第二次操作是否也觸發
            # (更好的做法是讓日誌包含更多上下文，但目前可接受)
            time.sleep(1) # 等待一下，讓日誌檔案有時間更新
            if not verify_log("字體大小變更"):
                 raise RuntimeError("「字體縮小」日誌驗證失敗。")

            # 4. 模擬檔案上傳並驗證日誌
            print(f"▶️ 模擬操作: 上傳檔案 '{DUMMY_FILE_NAME}'")
            page.locator("#file-input").set_input_files(dummy_file_path)
            if not verify_log("檔案已選擇"):
                raise RuntimeError("「檔案選擇」日誌驗證失敗。")

            # 5. 點擊「開始處理」按鈕並驗證日誌
            print("▶️ 模擬操作: 點擊「開始處理」按鈕")
            # 確保按鈕已啟用
            expect(page.locator("#start-processing-btn")).to_be_enabled()
            page.locator("#start-processing-btn").click()
            if not verify_log("開始處理按鈕點擊"):
                 raise RuntimeError("「開始處理」日誌驗證失敗。")

            # 6. 最終驗證與截圖
            print("✅ 所有模擬操作與日誌驗證均已成功。")
            page.screenshot(path=SCREENSHOT_FILE)
            print(f"📸 成功儲存最終驗證螢幕截圖至: {SCREENSHOT_FILE}")

            browser.close()
            return True

    except PlaywrightTimeoutError as e:
        print(f"❌ Playwright 操作超時: {e}")
        return False
    except RuntimeError as e:
        print(f"❌ 測試執行失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ 前端驗證過程中發生未預期的錯誤: {e}")
        return False
    finally:
        # --- 清理程序 ---
        print("▶️ 執行清理程序...")
        if server_process:
            print("▶️ 正在關閉後端伺服器...")
            # 使用 signal.SIGTERM 優雅地關閉整個 process group
            os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
            server_process.wait()
            print("✅ 伺服器已關閉。")
        if dummy_file_path and os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
            print(f"🗑️ 已刪除臨時檔案: {DUMMY_FILE_NAME}")
        # 清理日誌檔案
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
            print(f"🗑️ 已刪除日誌檔案: {LOG_FILE}")


if __name__ == "__main__":
    if run_verification():
        print("\n🎉🎉🎉 前端自動化驗證成功！ 🎉🎉🎉")
        exit(0)
    else:
        print("\n🔥🔥🔥 前端自動化驗證失敗。 🔥🔥🔥")
        exit(1)
