import requests
import time
import pytest
from pathlib import Path
import shutil

# 由於我們需要直接與資料庫互動來驗證結果，因此匯入 database 模組
from db import database

# --- 常數設定 ---
# 該測試現在假定伺服器已由外部程序 (如 circus) 啟動
TEST_PORT = 42649
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

# --- Fixture ---
@pytest.fixture(scope="function")
def setup_teardown_db():
    """
    一個在每次測試執行前後運行的 fixture，用於設定和清理資料庫。
    這確保了每個測試都在一個乾淨的環境中運行。
    """
    # --- Setup ---
    # 為了隔離，我們將在一個臨時目錄中進行測試
    # 注意：由於 api_server 和 db_manager 是由 circus 啟動的，
    # 它們會使用原始的 db/queue.db 路徑。
    # 因此，這個測試需要直接操作那個資料庫檔案。
    db_file = Path("db/queue.db")

    # 備份現有的資料庫 (如果存在)
    backup_file = db_file.with_suffix(".db.bak")
    if db_file.exists():
        shutil.copy(db_file, backup_file)

    # 刪除舊資料庫並重新初始化，以確保一個乾淨的狀態
    if db_file.exists():
        db_file.unlink()
    database.initialize_database()

    yield

    # --- Teardown ---
    # 刪除測試中建立的資料庫
    if db_file.exists():
        db_file.unlink()

    # 還原備份
    if backup_file.exists():
        shutil.move(str(backup_file), db_file)


def test_log_action_endpoint_writes_to_database(setup_teardown_db):
    """
    測試 `/api/log/action` 端點是否能正確地將日誌寫入資料庫。
    """
    # --- 0. 檢查伺服器是否正在運行 ---
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        assert response.status_code == 200, "API 伺服器健康檢查失敗。"
    except requests.ConnectionError:
        pytest.fail(f"無法連線至 API 伺服器 ({BASE_URL})。")

    # --- 1. 定義測試用的日誌訊息 ---
    test_action = f"db_logging_test_action_{int(time.time())}"
    payload = {"action": test_action}
    log_endpoint_url = f"{BASE_URL}/api/log/action"

    # --- 2. 發送 POST 請求 ---
    try:
        response = requests.post(log_endpoint_url, json=payload, timeout=10)
        assert response.status_code == 200
        assert response.json()["status"] == "logged"
    except requests.RequestException as e:
        pytest.fail(f"向日誌端點發送請求時失敗: {e}")

    # --- 3. 驗證資料庫內容 ---
    # 給予日誌處理器一點時間來完成寫入操作
    time.sleep(0.5)

    # 從資料庫中讀取日誌
    # 我們預期日誌的來源是 'frontend_action'
    logs = database.get_system_logs_by_filter(sources=['frontend_action'])

    # 斷言我們找到了日誌
    assert logs, "資料庫中應至少有一條來自 'frontend_action' 的日誌"

    # 檢查最新的一條日誌是否包含我們的測試訊息
    latest_log = logs[-1] # get_system_logs_by_filter 預設按時間升序排序
    assert latest_log['source'] == 'frontend_action'
    assert latest_log['level'] == 'INFO'
    assert test_action in latest_log['message'], f"在最新的日誌訊息中找不到預期的內容 '{test_action}'"

    print(f"✅ 成功驗證日誌訊息 '{test_action}' 已被寫入資料庫。")
