import requests
import os
import time
from pathlib import Path
import pytest

# --- 常數設定 ---
ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT_DIR / "run_log.txt"
# 該測試現在假定伺服器已由外部程序 (如 circus) 啟動
# 我們將使用 E2E 測試的固定埠號
TEST_PORT = 42649
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

@pytest.fixture(scope="function")
def setup_teardown():
    """
    一個在每次測試執行前後運行的 fixture，用於清理日誌檔案。
    """
    # --- Setup ---
    # 在測試前，確保日誌檔案是乾淨的
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    yield

    # --- Teardown ---
    # 在測試後，再次清理日誌檔案
    if LOG_FILE.exists():
        LOG_FILE.unlink()

def test_log_action_endpoint(setup_teardown):
    """
    測試 `/api/log/action` 端點是否能正確接收請求並寫入日誌。
    此測試假定 API 伺服器已在外部運行。

    Args:
        setup_teardown: pytest fixture，用於清理日誌。
    """
    # --- 0. 檢查伺服器是否正在運行 ---
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200, "API 伺服器健康檢查失敗。"
    except requests.ConnectionError:
        pytest.fail(f"無法連線至 API 伺服器 ({BASE_URL})。請確保服務已透過 'run_for_playwright.py' 啟動。")

    # --- 1. 定義測試用的日誌訊息 ---
    test_action = "fast_integration_test_action_98765"
    payload = {"action": test_action}
    log_endpoint_url = f"{BASE_URL}/api/log/action"

    # --- 2. 發送 POST 請求 ---
    try:
        response = requests.post(log_endpoint_url, json=payload, timeout=10)
        # 檢查請求是否成功
        assert response.status_code == 200
        assert response.json()["status"] == "logged"
    except requests.RequestException as e:
        pytest.fail(f"向日誌端點發送請求時失敗: {e}")

    # --- 3. 驗證日誌檔案內容 ---
    # 給予檔案系統一點時間來完成寫入操作
    time.sleep(0.5)

    # 檢查日誌檔案是否存在
    assert LOG_FILE.exists(), f"日誌檔案 {LOG_FILE} 未被建立！"

    # 讀取日誌內容並驗證
    log_content = LOG_FILE.read_text(encoding="utf-8")

    expected_log_entry = f"[FRONTEND ACTION] {test_action}"
    assert expected_log_entry in log_content, f"在日誌檔案中找不到預期的日誌訊息 '{expected_log_entry}'"

    print(f"✅ 成功驗證日誌訊息 '{test_action}' 已被寫入。")
