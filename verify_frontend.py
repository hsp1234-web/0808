import time
import os
import wave
import base64
from playwright.sync_api import sync_playwright, expect

def create_dummy_wav(filename="dummy_audio.wav"):
    """建立一個簡短的、無聲的 WAV 檔案用於測試上傳。"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 16000 * 1) # 1 秒的靜音
    return os.path.abspath(filename)

def run_verification():
    """
    使用 Playwright 執行前端自動化驗證。
    採用 Base64 注入檔案的方式，以繞過圖形介面檔案選擇器。
    """
    dummy_file_path = None
    try:
        dummy_file_path = create_dummy_wav()

        with open(dummy_file_path, "rb") as f:
            # 步驟 1: 讀取檔案並編碼為 Base64
            file_content_b64 = base64.b64encode(f.read()).decode('utf-8')

        with sync_playwright() as p:
            print("▶️ 啟動瀏覽器...")
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.set_default_timeout(60000)

            print("▶️ 導航至應用程式頁面...")
            page.goto("http://0.0.0.0:8000/static/mp3.html")

            print("▶️ 透過 JavaScript 注入 Base64 編碼的檔案...")
            # 步驟 2: 定義將在瀏覽器中執行的 JavaScript 程式碼片段
            js_script = """
            async ({ base64, fileName, mimeType }) => {
                // 將 Base64 解碼為 byte array
                const byteCharacters = atob(base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: mimeType });

                // 從 Blob 建立一個 File 物件
                const file = new File([blob], fileName, { type: mimeType });

                // 建立一個 DataTransfer 物件來模擬檔案選擇/拖放
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);

                // 找到目標 input 元素並將檔案指派給它
                const inputElement = document.getElementById('file-input');
                inputElement.files = dataTransfer.files;

                // 手動觸發 change 事件，以通知 Vue.js 檔案已變更
                inputElement.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """

            # 步驟 3: 執行 JavaScript
            page.evaluate(js_script, {
                "base64": file_content_b64,
                "fileName": os.path.basename(dummy_file_path),
                "mimeType": "audio/wav"
            })

            print("▶️ 驗證任務卡片是否出現...")
            task_card_locator = f'div.p-3:has-text("{os.path.basename(dummy_file_path)}")'
            task_card = page.locator(task_card_locator)
            expect(task_card).to_be_visible()
            print("✅ 任務卡片已成功顯示。")

            print("▶️ 等待任務完成...")
            status_indicator = task_card.locator('span.text-green-500:has-text("已完成")')
            expect(status_indicator).to_be_visible(timeout=30000)
            print("✅ 任務狀態已更新為「已完成」。")

            print("▶️ 擷取最終驗證螢幕截圖...")
            page.screenshot(path="verification.png")
            print("✅ 成功儲存螢幕截圖至 verification.png")

            browser.close()
            return True

    except Exception as e:
        print(f"❌ 前端驗證過程中發生錯誤: {e}")
        # 附加詳細的 Playwright 日誌以供偵錯
        try:
            print("\n--- Playwright Log ---")
            print(e.playwright_log)
            print("--- End Playwright Log ---")
        except:
            pass
        return False
    finally:
        # 清理臨時檔案
        if dummy_file_path and os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
            print(f"🗑️ 已刪除臨時檔案: {os.path.basename(dummy_file_path)}")

if __name__ == "__main__":
    if run_verification():
        print("\n🎉 前端驗證成功！")
    else:
        print("\n🔥 前端驗證失敗。")
        exit(1)
