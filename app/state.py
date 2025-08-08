# app/state.py
import time
import threading

# 建立一個執行緒安全的鎖，用於保護對共享狀態的存取
state_lock = threading.Lock()

# 共享狀態物件
# 我們將其初始化為閒置狀態，因為 worker 啟動時還沒有任務
shared_state = {
    # 'IDLE' (閒置) 或 'BUSY' (忙碌)
    "worker_status": "IDLE",
    # 記錄 worker 上次活動 (接到任務或回報心跳) 的時間戳
    "last_heartbeat": time.time()
}

def update_worker_status(status: str):
    """
    安全地更新 worker 的狀態和心跳時間。

    Args:
        status (str): 新的狀態，應為 'IDLE' 或 'BUSY'。
    """
    with state_lock:
        shared_state["worker_status"] = status
        shared_state["last_heartbeat"] = time.time()

def get_worker_status():
    """
    安全地讀取 worker 的完整狀態。

    Returns:
        dict: 包含 'worker_status' 和 'last_heartbeat' 的字典。
    """
    with state_lock:
        # 回傳一個副本以防止外部修改
        return shared_state.copy()
