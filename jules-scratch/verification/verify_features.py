import re
from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        port = 60481
        base_url = f"http://127.0.0.1:{port}"

        try:
            print(f"Navigating to {base_url}...")
            page.goto(base_url, timeout=10000)

            print("Verifying dashboard stats update...")
            # 1. Verify dashboard stats update
            cpu_label = page.locator("#cpu-label")
            expect(cpu_label).not_to_have_text("--%", timeout=10000)
            print("✅ Dashboard stats are updating.")

            print("Verifying 'tiny' model preload...")
            # 2. Verify 'tiny' model preload progress bar
            model_progress_text = page.locator("#model-progress-text")
            # Expect it to show starting/downloading for 'tiny'
            expect(model_progress_text).to_contain_text("模型 'tiny'", timeout=10000)
            # Expect it to eventually disappear
            expect(model_progress_text).to_be_hidden(timeout=20000)
            print("✅ 'tiny' model preload sequence verified.")

            print("Triggering 'base' model download...")
            # 3. Trigger 'base' model download
            page.get_by_label("模型大小").select_option("base")
            page.get_by_role("button", name="✓ 確認設定").click()

            print("Verifying 'base' model download progress bar...")
            # 4. Verify 'base' model progress bar appears
            expect(model_progress_text).to_contain_text("模型 'base'", timeout=10000)
            expect(model_progress_text).to_be_visible()
            print("✅ 'base' model download triggered and progress bar is visible.")

            # 5. Take screenshot
            screenshot_path = "jules-scratch/verification/verification.png"
            page.screenshot(path=screenshot_path)
            print(f"📸 Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred during verification: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
