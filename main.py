# main.py

"""
主執行腳本

用於模擬外部請求，觸發整個後端服務鏈路，以生成結構化日誌。
"""

from services import api_server
import logging

def run_simulation():
    """
    運行一系列模擬請求。
    """
    print("--- 開始模擬 ---")

    # 模擬 1: 一個成功的標準請求
    print("\n[模擬 1] 發送一個成功的標準請求...")
    api_server.handle_request({"user_id": "user-123", "action": "get_profile"})

    # 模擬 2: 另一個成功的請求，以產生不同的 correlation_id
    print("\n[模擬 2] 發送另一個成功的請求...")
    api_server.handle_request({"user_id": "user-456", "action": "update_settings", "values": {"theme": "dark"}})

    # 模擬 3: 一個預期會失敗的請求
    print("\n[模擬 3] 發送一個將在 Worker 中失敗的請求...")
    try:
        api_server.handle_request({"user_id": "user-789", "action": "create_report", "should_fail": True})
    except ValueError as e:
        # 在真實情境中，最上層的錯誤處理器會捕捉到這個異常
        # 我們在這裡印出訊息，模擬該行為
        print(f"模擬客戶端捕獲到預期的錯誤: {e}")

    print("\n--- 模擬結束 ---")
    print(f"\n所有日誌已寫入 'logs/backend.log'。")
    print("您現在可以使用 'create_evidence_package.py' 來提取特定請求的日誌。")

if __name__ == "__main__":
    # 在開始模擬前，確保日誌檔案是乾淨的（可選）
    # import os
    # if os.path.exists("logs/backend.log"):
    #     os.remove("logs/backend.log")

    # 確保 root logger 不會干擾我們的設定
    logging.basicConfig(level=logging.CRITICAL)
    run_simulation()
