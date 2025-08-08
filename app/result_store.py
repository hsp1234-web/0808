# app/result_store.py
import threading
from typing import Dict, Any

# 這是一個簡單的、執行緒安全的記憶體內結果儲存區。
# 它使用一個字典來儲存每個任務的狀態和結果。
# 鎖 (threading.Lock) 用於確保在多個執行緒（Web 伺服器和工作者）同時存取時的資料一致性。

# 結構範例:
# {
#   "task_123": {"status": "processing", "result": None},
#   "task_456": {"status": "complete", "result": "這是轉錄文字。"},
#   "task_789": {"status": "error", "result": "模型載入失敗。"}
# }

_results: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()

def set_status(task_id: str, status: str, result: Any = None):
    """設定指定任務的狀態和結果。"""
    with _lock:
        if task_id not in _results:
            _results[task_id] = {}
        _results[task_id]['status'] = status
        if result is not None:
            _results[task_id]['result'] = result

def get_status(task_id: str) -> Dict[str, Any] | None:
    """取得指定任務的狀態和結果。"""
    with _lock:
        return _results.get(task_id)
