import requests
import time
import pytest

# --- 常數設定 ---
# 該測試現在假定伺服器已由外部程序 (如 circus) 啟動
# 我們將使用 E2E 測試的固定埠號
TEST_PORT = 42649
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

def test_log_action_endpoint_to_database():
    """
    測試 `/api/log/action` 端點是否能正確接收請求，並將其記錄到資料庫中。
    此測試假定 API 伺服器和資料庫管理者已在外部運行。
    """
    # --- 0. 檢查伺服器是否正在運行 ---
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200, "API 伺服器健康檢查失敗。"
    except requests.ConnectionError:
        pytest.fail(f"無法連線至 API 伺服器 ({BASE_URL})。請確保服務已透過 'run_tests.py' 或類似腳本啟動。")

    # --- 1. 定義測試用的日誌訊息 ---
    # 使用一個獨特的字串以避免與其他測試的日誌混淆
    test_action = f"db_logging_test_action_{int(time.time())}"
    payload = {"action": test_action}
    log_endpoint_url = f"{BASE_URL}/api/log/action"

    # --- 2. 發送 POST 請求來觸發日誌記錄 ---
    try:
        response = requests.post(log_endpoint_url, json=payload, timeout=10)
        assert response.status_code == 200
        assert response.json()["status"] == "logged"
    except requests.RequestException as e:
        pytest.fail(f"向日誌端點發送請求時失敗: {e}")

    # --- 3. 透過偵錯端點驗證日誌是否已寫入資料庫 ---
    # 給予日誌處理器一點時間來完成非同步的寫入操作
    time.sleep(0.5)

    debug_log_endpoint = f"{BASE_URL}/api/debug/latest_frontend_action_log"
    try:
        response = requests.get(debug_log_endpoint, timeout=10)
        assert response.status_code == 200, f"偵錯日誌端點回傳了非 200 的狀態碼: {response.status_code}"

        response_data = response.json()
        assert "latest_log" in response_data, "偵錯日誌端點的回應中缺少 'latest_log' 欄位。"

        latest_log = response_data["latest_log"]
        assert latest_log is not None, "資料庫中沒有找到任何 'frontend_action' 來源的日誌。"

        # 驗證日誌內容
        assert "message" in latest_log, "日誌物件中缺少 'message' 欄位。"
        log_message = latest_log["message"]
        assert log_message == test_action, f"最新的日誌訊息與預期的不符。預期: '{test_action}', 實際: '{log_message}'"

        assert latest_log.get("source") == "frontend_action", f"日誌來源不正確。預期: 'frontend_action', 實際: '{latest_log.get('source')}'"

    except requests.RequestException as e:
        pytest.fail(f"向偵錯日誌端點發送請求時失敗: {e}")

    print(f"✅ 成功驗證日誌訊息 '{test_action}' 已被寫入資料庫。")
