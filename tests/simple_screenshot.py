from playwright.sync_api import sync_playwright
import os

PORT = 49243
APP_URL = f"http://127.0.0.1:{PORT}/"
SCREENSHOT_DIR = "test-results"
SCREENSHOT_FILE = f"{SCREENSHOT_DIR}/simple_test.png"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print(f"Navigating to {APP_URL}")
    page.goto(APP_URL)
    print(f"Taking screenshot to {SCREENSHOT_FILE}")
    page.screenshot(path=SCREENSHOT_FILE)
    print("Screenshot taken.")
    browser.close()

print(f"Script finished. Check for file: {SCREENSHOT_FILE}")
