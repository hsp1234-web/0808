import asyncio
import re
from playwright.async_api import async_playwright, expect

async def main():
    """
    此測試腳本旨在端對端驗證 YouTube 報告頁面的修復情況。
    它會執行以下操作：
    1. 導覽至 YouTube 報告頁面。
    2. 輸入並儲存使用者提供的 Gemini API 金鑰。
    3. 等待模型列表載入，並選擇指定的 "Flash-2.0" 模型。
    4. 輸入使用者提供的 Bilibili 影片網址。
    5. 啟動分析流程。
    6. 等待並驗證任務完成，報告出現在瀏覽區。
    7. 點擊預覽按鈕。
    8. 截取最終的預覽彈窗畫面，以證明修復成功。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 使用者提供的資料
            gemini_api_key = "AIzaSyBdw0gY2oh2W_r1eN3ALzK9RCAAcedgF3E"
            video_url = "https://b23.tv/6FjXRsx"
            target_model_text = "flash-2.0"
            final_screenshot_path = "final_youtube_fix_verification.jpg"

            print(">>> 步驟 1/8: 導覽至 YouTube 報告頁面...")
            await page.goto("http://localhost:8000/youtube", timeout=30000)

            print(f">>> 步驟 2/8: 輸入並儲存 API 金鑰: ...{gemini_api_key[-4:]}")
            await page.locator("#api-key-input").fill(gemini_api_key)
            await page.locator("#save-api-key-btn").click()

            print(">>> 步驟 3/8: 等待金鑰驗證成功並載入模型...")
            # 等待 "金鑰有效" 的狀態出現，給予足夠的時間讓後端驗證
            await expect(page.locator("#api-key-status > span")).to_have_text("金鑰有效，Gemini 功能已啟用", timeout=20000)

            print(f">>> 步驟 4/8: 選擇包含 '{target_model_text}' 的模型...")
            select_element = page.locator("#gemini-model-select")
            await expect(select_element).to_be_enabled(timeout=10000)

            # 手動尋找匹配的選項
            all_options = await select_element.locator("option").all_inner_texts()
            option_to_select = None
            for option_text in all_options:
                if re.search("2.0 Flash", option_text, re.IGNORECASE):
                    option_to_select = option_text
                    break

            if option_to_select:
                print(f"    - 找到匹配的模型: '{option_to_select}'. 正在選擇...")
                await select_element.select_option(label=option_to_select)
            else:
                raise Exception(f"在下拉選單中找不到包含 '2.0 Flash' 的模型。可用的選項: {all_options}")


            print(f">>> 步驟 5/8: 輸入影片網址: {video_url}")
            await page.locator(".youtube-url-input").first.fill(video_url)

            print(">>> 步驟 6/8: 點擊分析按鈕並等待任務完成...")
            await page.locator("#start-youtube-processing-btn").click()

            # 等待處理中任務出現 (給予一些時間讓任務啟動)
            await expect(page.locator("#ongoing-tasks .task-item")).to_be_visible(timeout=15000)
            print("    - 任務已出現在「處理中」列表。")

            # 等待處理中任務消失
            await expect(page.locator("#ongoing-tasks .task-item")).to_have_count(0, timeout=120000) # 給予足夠的處理時間 (2分鐘)
            print("    - 任務已從「處理中」列表消失。")

            print(">>> 步驟 7/8: 驗證報告是否出現在完成列表並點擊預覽...")
            # 驗證報告出現在瀏覽區
            report_item = page.locator("#youtube-file-browser .task-item").first
            await expect(report_item).to_be_visible(timeout=10000)
            print("    - 報告已成功出現在瀏覽區。")

            # 點擊預覽按鈕
            preview_button = report_item.locator('[data-testid="view-report-button"]')
            await preview_button.click()
            print("    - 已點擊預覽按鈕。")

            print(f">>> 步驟 8/8: 截取最終預覽畫面至 {final_screenshot_path}...")
            # 等待 Modal 彈窗出現
            modal = page.locator("#preview-modal")
            await expect(modal).to_be_visible(timeout=10000)

            # 截取 Modal 的畫面
            await modal.screenshot(path=final_screenshot_path, type="jpeg", quality=95)

            print("\n✅ 測試成功完成！")
            print(f"螢幕截圖已儲存於: {final_screenshot_path}")

        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            await page.screenshot(path="e2e_youtube_fix_error.jpg", full_page=True, type="jpeg", quality=90)
            print("已截取當前頁面快照至 e2e_youtube_fix_error.jpg")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
