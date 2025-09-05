import os
import re
from playwright.sync_api import sync_playwright, expect

def run_final_verification():
    """
    一個端對端驗證腳本，用於測試完整的 YouTube 報告生成流程。
    此版本已調整為可在 'mock' 模式下成功運行，並修復了控制台日誌捕獲的錯誤。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = browser.new_page()

        console_logs = []
        # JULES'S FIX (2025-09-04): 修正了 console 事件監聽器中的錯誤。
        # `msg.type` 和 `msg.text` 是屬性，不是方法。這個錯誤導致我們之前無法看到任何日誌。
        page.on("console", lambda msg: console_logs.append(f"BROWSER CONSOLE: [{msg.type}] {msg.text}"))

        try:
            # 在模擬模式下，任何非空字串都可以作為有效的 API 金鑰
            api_key = "mock_key_for_testing"
            youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

            print("--- 開始 E2E 驗證 (模擬模式) ---")

            page.goto('http://127.0.0.1:42649/youtube', timeout=60000)
            print(f"[OK] 導航至 /youtube")

            # 1. 儲存 API 金鑰並等待驗證成功
            page.get_by_test_id('api-key-input').fill(api_key)
            page.get_by_test_id('save-api-key-button').click()
            print(f"[OK] 已填入模擬 API 金鑰並點擊儲存")

            analyze_button = page.get_by_test_id('start-youtube-processing-button')
            print("     - 等待分析按鈕變為可點擊...")
            expect(analyze_button).to_be_enabled(timeout=10000)
            print(f"[OK] 分析按鈕已啟用")

            # 2. 輸入 YouTube URL 並開始分析
            page.locator('.youtube-url-input').first.fill(youtube_url)
            print(f"[OK] 已填入 YouTube URL: {youtube_url}")

            analyze_button.click()
            print(f"[OK] 已點擊分析按鈕，開始處理...")

            # 3. 等待報告產生
            print("     - 等待模擬報告出現在瀏覽區...")
            view_report_button = page.get_by_test_id('view-report-button').first
            expect(view_report_button).to_be_visible(timeout=30000)
            print(f"[OK] 模擬報告已產生！")

            # 4. 打開報告並截圖
            view_report_button.click()
            print(f"[OK] 已點擊 '預覽' 按鈕")

            report_modal = page.get_by_test_id('report-modal')
            print("     - 等待報告 Modal 彈出...")
            expect(report_modal).to_be_visible(timeout=10000)
            print(f"[OK] 報告 Modal 已顯示")

            page.wait_for_timeout(2000)

            # 5. 截圖
            screenshot_path = 'final_screenshot.jpg'
            report_modal.screenshot(path=screenshot_path)
            print(f"✅ 驗證成功！報告螢幕截圖已儲存至: {screenshot_path}")

        except Exception as e:
            print(f"\n❌ 驗證過程中發生錯誤: {e}")
            page.screenshot(path='e2e_error.jpg', full_page=True)
            print("已儲存錯誤時的截圖: e2e_error.jpg")

        finally:
            print("\n--- 瀏覽器控制台日誌 ---\n")
            if console_logs:
                for log in console_logs:
                    print(log)
            else:
                print("未捕獲到任何控制台日誌。")
            print("\n--- 控制台日誌結束 ---\n")
            browser.close()
            print("--- E2E 驗證腳本執行完畢 ---")

if __name__ == "__main__":
    run_final_verification()
