# coding: utf-8
"""
app/state.py

說明:
本模組用於定義一個全域共享的狀態物件，以便在應用程式的不同部分
（例如，主監控腳本和背景工作者）之間安全地傳遞資訊。

主要功能：
- 提供一個集中式的字典來儲存應用程式狀態，如工作者的忙碌/閒置狀態和心跳時間。
- 使用執行緒鎖 (threading.Lock) 來確保對共享狀態的存取是執行緒安全的，防止競態條件。
"""
import time
import threading

# 執行緒鎖，用於保護對 `shared_state` 的並行存取
state_lock = threading.Lock()

# 全域共享狀態字典
# - worker_status: 工作者的目前狀態 ('idle', 'busy', 'starting', 'stopping')
# - last_heartbeat: 工作者上次回報心跳的 UNIX 時間戳
shared_state = {
    "worker_status": "starting",
    "last_heartbeat": time.time()
}

def update_worker_status(status: str, heartbeat: bool = True):
    """
    安全地更新工作者的狀態。

    Args:
        status (str): 新的狀態 ('idle', 'busy', 'stopping')。
        heartbeat (bool): 是否同時更新心跳時間戳。
    """
    global shared_state
    with state_lock:
        shared_state["worker_status"] = status
        if heartbeat:
            shared_state["last_heartbeat"] = time.time()

def get_worker_state() -> dict:
    """
    安全地獲取整個工作者狀態的副本。

    Returns:
        dict: 目前共享狀態的一個淺層副本。
    """
    with state_lock:
        return shared_state.copy()
