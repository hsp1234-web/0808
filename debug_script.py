import asyncio
from playwright.async_api import async_playwright

async def main():
    """
    此腳本用於除錯前端 JavaScript 的執行流程。
    它會監聽瀏覽器的 console.log 輸出，幫助我們追蹤程式碼是否被執行。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 設定 console 事件監聽器
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))

        print(">>> 正在導覽至頁面...")
        await page.goto("http://localhost:8000/youtube")

        print(">>> 正在點擊 #save-api-key-btn 按鈕...")
        try:
            await page.locator("#save-api-key-btn").click(timeout=5000)
            print(">>> 點擊操作已送出。")
        except Exception as e:
            print(f"點擊失敗: {e}")

        # 等待幾秒鐘以確保所有 console.log 都有時間被觸發和印出
        print(">>> 等待 3 秒以擷取日誌...")
        await asyncio.sleep(3)

        print(">>> 除錯腳本執行完畢。")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
