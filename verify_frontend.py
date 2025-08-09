import time
import os
import wave
import base64
import subprocess
import requests
from playwright.sync_api import sync_playwright, expect

def create_dummy_wav(filename="dummy_audio.wav"):
    """建立一個簡短的、無聲的 WAV 檔案用於測試上傳。"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * 16000 * 1) # 1 秒的靜音
    return os.path.abspath(filename)

def wait_for_server(url, timeout=30):
    """等待後端伺服器啟動。"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print("✅ 伺服器已成功啟動。")
                return True
        except requests.ConnectionError:
            time.sleep(0.5)
    print(f"❌ 伺服器在 {timeout} 秒內沒有回應。")
    return False

def run_verification():
    """
    使用 Playwright 執行前端自動化驗證。
    """
    server_process = None
    dummy_file_path = None
    try:
        # 啟動後端伺服器
        print("▶️ 啟動後端伺服器...")
        server_process = subprocess.Popen(["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"])

        # 等待伺服器啟動
        if not wait_for_server("http://0.0.0.0:8000/api/system_stats"):
            raise RuntimeError("後端伺服器啟動失敗。")

        dummy_file_path = create_dummy_wav()
        with open(dummy_file_path, "rb") as f:
            file_content_b64 = base64.b64encode(f.read()).decode('utf-8')

        with sync_playwright() as p:
            print("▶️ 啟動瀏覽器...")
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.set_default_timeout(30000) # 設定預設超時

            print("▶️ 導航至應用程式頁面...")
            page.goto("http://0.0.0.0:8000/static/mp3.html", wait_until="domcontentloaded")

            # --- 字體大小測試 ---
            print("▶️ 測試字體大小調整功能...")
            font_size_display = page.locator('span.font-bold:has-text("%")')
            zoom_in_button = page.locator('button:has(i[data-lucide="zoom-in"])')
            zoom_out_button = page.locator('button:has(i[data-lucide="zoom-out"])')

            # 初始狀態截圖
            page.screenshot(path="verification_fontsize_initial.png")
            print("📸 已擷取初始狀態螢幕截圖。")
            initial_font_size = font_size_display.inner_text()
            print(f"初始字體大小: {initial_font_size}")
            expect(font_size_display).to_have_text("100%")

            # 點擊放大
            zoom_in_button.click()
            page.wait_for_timeout(500) # 等待動畫
            page.screenshot(path="verification_fontsize_zoomed_in.png")
            zoomed_in_font_size = font_size_display.inner_text()
            print(f"放大後字體大小: {zoomed_in_font_size}")
            print("📸 已擷取放大後螢幕截圖。")
            expect(font_size_display).to_have_text("125%")

            # 點擊縮小
            zoom_out_button.click()
            zoom_out_button.click() # 點兩次回到 75%
            page.wait_for_timeout(500)
            page.screenshot(path="verification_fontsize_zoomed_out.png")
            zoomed_out_font_size = font_size_display.inner_text()
            print(f"縮小後字體大小: {zoomed_out_font_size}")
            print("📸 已擷取縮小後螢幕截圖。")
            expect(font_size_display).to_have_text("75%")

            print("✅ 字體大小調整功能測試完成。")

            # --- 檔案上傳與處理測試 ---
            print("▶️ 執行檔案上傳與處理流程...")
            # (此處省略了與之前版本相同的 base64 注入程式碼)
            js_script = """
            async ({ base64, fileName, mimeType }) => {
                const byteCharacters = atob(base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                const blob = new Blob([byteArray], { type: mimeType });
                const file = new File([blob], fileName, { type: mimeType });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                const inputElement = document.getElementById('file-input');
                inputElement.files = dataTransfer.files;
                inputElement.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """
            page.evaluate(js_script, {
                "base64": file_content_b64,
                "fileName": os.path.basename(dummy_file_path),
                "mimeType": "audio/wav"
            })

            print("▶️ 點擊「開始處理」按鈕...")
            start_button = page.locator('button:has-text("開始處理")')
            start_button.click()

            print("▶️ 等待任務完成...")
            completed_selector = f'div.p-3:has-text("{os.path.basename(dummy_file_path)}")'
            expect(page.locator(completed_selector)).to_be_visible(timeout=60000)
            print("✅ 任務已成功顯示在「已完成」列表中。")

            print("▶️ 擷取最終驗證螢幕截圖...")
            page.screenshot(path="verification_final.png")
            print("✅ 成功儲存螢幕截圖至 verification_final.png")

            browser.close()
            return True

    except Exception as e:
        print(f"❌ 前端驗證過程中發生錯誤: {e}")
        return False
    finally:
        # 確保伺服器和臨時檔案都被清理
        if server_process:
            print("▶️ 正在關閉後端伺服器...")
            server_process.terminate()
            server_process.wait()
            print("✅ 伺服器已關閉。")
        if dummy_file_path and os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)
            print(f"🗑️ 已刪除臨時檔案: {os.path.basename(dummy_file_path)}")

if __name__ == "__main__":
    if run_verification():
        print("\n🎉 前端驗證成功！")
    else:
        print("\n🔥 前端驗證失敗。")
        exit(1)
