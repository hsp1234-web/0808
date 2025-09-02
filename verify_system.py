import time
import httpx
import sys
from pathlib import Path
import json
import os

# --- 設定 ---
# 將專案的 src 目錄新增到 Python 的搜尋路徑中
# 這樣才能正確找到 db.client 等模組。
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

try:
    from db.client import get_client
except ImportError as e:
    print(f"無法匯入 db.client: {e}")
    print("請確認您是從專案的根目錄執行此腳本。")
    sys.exit(1)

# API 伺服器的 URL，從環境變數讀取或使用預設值
# 這允許我們在執行 `orchestrator.py` 時傳入的 --port 能被測試腳本感知
# 예: API_PORT=8001 python verify_system.py
API_PORT = os.environ.get("API_PORT", "8001")
API_URL = f"http://127.0.0.1:{API_PORT}"

def run_test():
    """執行所有驗證步驟。"""
    print(f"--- 測試目標伺服器: {API_URL} ---\n")
    db_client = get_client()

    print("--- 步驟 1: 清理舊狀態 ---")
    try:
        db_client.clear_all_tasks()
        # 將心跳設定為一個可識別的初始值
        db_client.set_app_state("worker_last_heartbeat", "0")
        print("✅ 舊任務與心跳狀態已清理。")
    except Exception as e:
        print(f"❌ 清理時發生錯誤: {e}")
        print("請確認資料庫管理者 (db/manager.py) 是否正在運行。")
        sys.exit(1)

    print("\n--- 步驟 2: 等待系統啟動與 Worker 第一次心跳 ---")
    print("⏳ 等待 20 秒...")
    time.sleep(20)

    print("\n--- 步驟 3: 檢查初始心跳 ---")
    initial_heartbeat_str = db_client.get_app_state("worker_last_heartbeat")
    if initial_heartbeat_str is None or float(initial_heartbeat_str) == 0:
        print("❌ 錯誤：Worker 啟動後沒有偵測到心跳！")
        print("請確認 src/core/orchestrator.py 是否已啟動，且 Worker 沒有在啟動時崩潰。")
        sys.exit(1)

    initial_heartbeat = float(initial_heartbeat_str)
    print(f"✅ 偵測到初始心跳: {initial_heartbeat}")

    print("\n--- 步驟 4: 提交一個新的轉錄任務 ---")
    # 在當前目錄建立一個用於上傳的臨時檔案
    dummy_file_path = ROOT_DIR / "test_audio_for_verify.txt"
    dummy_file_path.write_text("this is a simple test file for verification.")

    try:
        with open(dummy_file_path, "rb") as f:
            # 在模擬模式下，transcriber 會很快完成
            files = {"file": ("test_audio_for_verify.txt", f, "text/plain")}
            data = {"model_size": "tiny"}
            response = httpx.post(f"{API_URL}/api/transcribe", files=files, data=data, timeout=20)

        if response.status_code != 202:
            print(f"❌ 提交任務失敗，狀態碼: {response.status_code}, 回應: {response.text}")
            sys.exit(1)

        task_id = response.json()["task_id"]
        print(f"✅ 任務已成功提交，Task ID: {task_id}")
    except httpx.RequestError as e:
        print(f"❌ 提交任務時發生網路錯誤: {e}")
        print(f"請確認 API 伺服器 ({API_URL}) 是否正在運行。")
        sys.exit(1)
    finally:
        # 清理臨時檔案
        if dummy_file_path.exists():
            dummy_file_path.unlink()

    print("\n--- 步驟 5: 等待任務處理與心跳更新 ---")
    print("⏳ 等待 25 秒...")
    time.sleep(25)

    print("\n--- 步驟 6: 驗證任務結果 ---")
    try:
        response = httpx.get(f"{API_URL}/api/status/{task_id}", timeout=10)
        if response.status_code != 200:
            print(f"❌ 獲取任務狀態失敗，狀態碼: {response.status_code}, 回應: {response.text}")
            sys.exit(1)

        status_data = response.json()
        if status_data["status"] != "completed":
            print(f"❌ 任務狀態不是 'completed'，而是 '{status_data['status']}'")
            print("請檢查 Worker 的日誌輸出以了解詳細錯誤。")
            sys.exit(1)

        print("✅ 任務已成功完成！")
    except httpx.RequestError as e:
        print(f"❌ 獲取任務狀態時發生網路錯誤: {e}")
        sys.exit(1)

    print("\n--- 步驟 7: 驗證心跳更新 ---")
    final_heartbeat_str = db_client.get_app_state("worker_last_heartbeat")
    final_heartbeat = float(final_heartbeat_str)

    if not (final_heartbeat > initial_heartbeat):
        print(f"❌ 錯誤：心跳時間戳沒有更新！(舊: {initial_heartbeat}, 新: {final_heartbeat})")
        sys.exit(1)

    print(f"✅ 心跳已成功更新: (舊: {initial_heartbeat}, 新: {final_heartbeat})")

    print("\n\n🎉🎉🎉 系統核心功能（心跳與新架構）驗證成功！🎉🎉🎉")


if __name__ == "__main__":
    print("="*60)
    print("鳳凰專案 - v5.0 架構端到端驗證腳本")
    print("="*60)
    print("本腳本將會執行以下操作：")
    print("1. 清理資料庫狀態")
    print("2. 檢查 Worker 的初始心跳")
    print("3. 提交一個模擬的轉錄任務")
    print("4. 驗證任務是否被 Worker 成功處理")
    print("5. 驗證 Worker 的心跳是否在持續更新")
    print("\n**請在執行此腳本前，於另一個終端機啟動系統：**")
    print("`python src/core/orchestrator.py --mock`")
    print("(建議使用 --mock 模式以獲得最快的測試結果)")
    print("="*60)

    try:
        # 腳本說明已提示使用者預先啟動 orchestrator。
        # 我們在此處增加一個短暫延遲，給予服務啟動的時間。
        print("\n給予系統 5 秒啟動時間...")
        time.sleep(5)
        run_test()
    except KeyboardInterrupt:
        print("\n使用者中斷操作。")
        sys.exit(0)
