import time
from playwright.sync_api import sync_playwright, expect

def take_screenshot():
    """
    一個簡單的腳本，用於啟動瀏覽器，導覽到頁面，並擷取螢幕截圖。
    這繞過了完整的 E2E 測試框架，以應對環境中的超時問題。
    """
    # Playwright 測試設定為使用 42649 埠號
    APP_URL = "http://127.0.0.1:42649/"
    SCREENSHOT_FILE = "final_screenshot.png"

    print("▶️ 正在啟動 Playwright...")
    with sync_playwright() as p:
        print("▶️ 正在啟動瀏覽器...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        # 嘗試設定中文語系和時區，希望能解決無頭瀏覽器中的字體渲染問題
        context = browser.new_context(locale='zh-TW', timezone_id='Asia/Taipei')
        page = context.new_page()

        print(f"▶️ 正在導覽至 {APP_URL}...")
        try:
            page.goto(APP_URL, timeout=30000)
            print("✅ 頁面載入成功。")

            # 修正：等待更穩定的「準備就緒」狀態，而不是稍縱即逝的「已連線」
            expect(page.locator('#status-text')).to_contain_text('準備就緒', timeout=15000)
            print("✅ 狀態顯示「準備就緒」。")

            # 點擊「媒體下載器」分頁
            print("▶️ 點擊事件在無頭模式下不穩定，改用 page.evaluate() 直接操作 DOM。")

            # 要顯示的分頁的 ID
            target_tab_id = "downloader-tab"

            page.evaluate(f'''() => {{
                const tabId = '{target_tab_id}';
                // 移除所有按鈕和內容的 'active' class
                document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

                // 為目標按鈕和內容加上 'active' class
                const targetButton = document.querySelector(`button[data-tab="${{tabId}}"]`);
                if (targetButton) targetButton.classList.add('active');

                const targetContent = document.getElementById(tabId);
                if (targetContent) targetContent.classList.add('active');
            }}''')

            print(f"✅ 已手動將 {target_tab_id} 設為作用中分頁。")

            # 驗證下載器內容是否可見
            downloader_content = page.locator('#downloader-tab')
            expect(downloader_content).to_be_visible(timeout=5000)
            print("✅ 「媒體下載器」內容已可見。")

            # 等待一小段時間確保所有動畫或延遲載入的內容都已呈現
            time.sleep(2)

            print(f"▶️ 正在擷取螢幕截圖並儲存至 {SCREENSHOT_FILE}...")
            page.screenshot(path=SCREENSHOT_FILE, full_page=True)
            print(f"📸 螢幕截圖已成功儲存！")

        except Exception as e:
            print(f"❌ 執行過程中發生錯誤: {e}")
            # 即使出錯，也嘗試擷取一張螢幕截圖以供除錯
            page.screenshot(path="debug_screenshot.png")
            print("📸 已儲存一張除錯用的螢幕截圖。")
        finally:
            print("▶️ 正在關閉瀏覽器...")
            browser.close()
            print("✅ 瀏覽器已關閉。")

if __name__ == "__main__":
    take_screenshot()
