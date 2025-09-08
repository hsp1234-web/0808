# db/manager.py
#
# --- 執行與管理說明 (由 Jules 於 2025-08-12 新增) ---
#
# **重要：** 此腳本不應該被直接執行。
#
# 本檔案定義了一個作為背景服務運行的 TCP 伺服器，負責管理所有資料庫操作。
# 為了避免因程序未被正確關閉而導致的資源衝突（即「殭屍程序」問題），
# 此服務的生命週期由 `circus` 程序管理器進行統一管理。
#
# **標準啟動方式：**
# 1. **透過 `run_tests.py`**：這是執行測試的標準方法。
#    `run_tests.py` 會自動處理以下所有步驟：
#      a. 清理舊的程序和檔案。
#      b. 使用 `circus` 啟動此 `db_manager` 和 `api_server`。
#      c. 執行 `pytest` 測試。
#      d. 在測試結束後，確保所有服務都被優雅關閉。
#
# 2. **手動啟動 (開發時)**：若需手動啟動，應使用 `circus`：
#    `python -m circus.circusd circus.ini`
#
# 透過 `run_tests.py` 或 `circus` 來管理，可以從根本上解決
# 因資源（埠號、資料庫檔案）被占用而導致的啟動失敗問題。
#
# --- 程式碼開始 ---
import socketserver
import json
import logging
import sqlite3
from pathlib import Path
import multiprocessing
import threading
import queue # 用於捕捉 queue.Empty 例外

# 讓此腳本可以存取上層目錄的 db.database 模組
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db import database

# --- 日誌設定 ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger('DBManagerServer')

# --- 伺服器設定 ---
HOST, PORT = "127.0.0.1", 49999

# --- 全域任務佇列 ---
# 使用 multiprocessing.Manager 來建立一個可在多個行程間共享的佇列
# 這使得我們的架構未來可以輕易地擴展到多個 Worker 行程
manager = multiprocessing.Manager()
task_queue = manager.Queue()

def enqueue_task(**params):
    """
    將一個任務放入全域的 multiprocessing 佇列中。
    這是一個非阻塞操作，API 伺服器可以立即獲得回應。
    """
    log.info(f"接收到任務，準備放入佇列: {params.get('task_id')}")
    task_queue.put(params)
    log.debug(f"目前佇列大小約為: {task_queue.qsize()}")
    return True # 立即成功返回

# --- 指令分派 ---
ACTION_MAP = {
    # --- 核心任務流程重構 ---
    # 新的入口點：將任務放入佇列，立即返回
    "enqueue_task": enqueue_task,
    # 舊的 add_task 已被移除，所有任務建立必須通過佇列
    "fetch_and_lock_task": database.fetch_and_lock_task,
    "unlock_task": database.unlock_task,
    "update_task_progress": database.update_task_progress,
    "update_task_status": database.update_task_status,
    "update_task_payload": database.update_task_payload,
    "get_task_status": database.get_task_status,
    "are_tasks_active": database.are_tasks_active,
    "get_all_tasks": database.get_all_tasks,
    "get_system_logs": database.get_system_logs_by_filter,
    "find_dependent_task": database.find_dependent_task,
    "get_app_state": database.get_app_state,
    "set_app_state": database.set_app_state,
    "get_all_app_states": database.get_all_app_states,
    "clear_all_tasks": database.clear_all_tasks,
}

def task_writer_thread(stop_event):
    """
    一個在背景執行的執行緒，負責從佇列中取出任務並寫入資料庫。
    """
    log.info("🚀 背景資料庫寫入執行緒已啟動。")
    while not stop_event.is_set():
        try:
            # 使用 timeout，這樣執行緒可以定期檢查 stop_event
            task_params = task_queue.get(timeout=1.0)
            log.info(f"從佇列中取出任務，準備寫入資料庫: {task_params}")
            database.add_task(**task_params)
            log.info(f"✅ 成功將任務 {task_params.get('task_id')} 寫入資料庫。")
        except queue.Empty:
            # 佇列為空是正常情況，繼續等待
            continue
        except Exception as e:
            log.error(f"❌ 資料庫寫入執行緒發生錯誤: {e}", exc_info=True)
            # 這裡可以加入更複雜的重試邏輯或將失敗的任務移至死信佇列
    log.info("背景資料庫寫入執行緒已停止。")


class DBRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        log.info(f"來自 {self.client_address} 的新連線。")
        try:
            while True:
                header = self.request.recv(4)
                if not header: break
                data_len = int.from_bytes(header, 'big')
                data = self.request.recv(data_len)
                if not data: break

                request = json.loads(data.decode('utf-8'))
                log.info(f"收到請求: {request}")

                action = request.get("action")
                params = request.get("params", {})
                response = {}

                try:
                    if action in ACTION_MAP:
                        func = ACTION_MAP[action]
                        result = func(**params)
                        response["status"] = "success"
                        response["data"] = result
                    else:
                        response["status"] = "error"
                        response["message"] = f"未知的 action: {action}"
                        log.warning(f"收到了未知的 action: {action}")
                except Exception as e:
                    log.error(f"執行 action '{action}' 時發生錯誤: {e}", exc_info=True)
                    response["status"] = "error"
                    response["message"] = f"執行 '{action}' 時發生內部錯誤: {str(e)}"

                response_bytes = json.dumps(response).encode('utf-8')
                response_header = len(response_bytes).to_bytes(4, 'big')
                self.request.sendall(response_header + response_bytes)
        except ConnectionResetError:
            log.warning(f"客戶端 {self.client_address} 強制中斷了連線。")
        except Exception as e:
            log.error(f"處理連線 {self.client_address} 時發生未預期的錯誤: {e}", exc_info=True)
        finally:
            log.info(f"連線 {self.client_address} 已關閉。")

def run_server():
    """
    啟動資料庫管理者伺服器，並包含背景寫入執行緒。
    """
    stop_event = threading.Event()
    writer_thread = None
    try:
        # ... (和之前一樣的檔案清理和資料庫初始化) ...
        try:
            log.info("資料庫管理者伺服器啟動前，正在進行資料庫初始化...")
            database.initialize_database()
            log.info("✅ 資料庫初始化成功。")
        except sqlite3.Error as e:
            log.critical(f"❌ 資料庫初始化失敗，伺服器無法啟動: {e}", exc_info=True)
            sys.exit(1)

        # 啟動背景寫入執行緒
        writer_thread = threading.Thread(target=task_writer_thread, args=(stop_event,))
        writer_thread.daemon = True # 確保主程序退出時，此執行緒也會退出
        writer_thread.start()

        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer((HOST, PORT), DBRequestHandler) as server:
            actual_port = server.server_address[1]
            log.info(f"🚀 資料庫管理者伺服器已在 {HOST}:{actual_port} 上啟動...")
            print(f"DB_MANAGER_PORT: {actual_port}", flush=True)
            print("DB_MANAGER_READY", flush=True)
            server.serve_forever()

    except Exception as e:
        log.critical(f"🚨 DB 管理者伺服器發生致命錯誤，即將關閉: {e}", exc_info=True)
        sys.exit(1)
    finally:
        log.info("正在關閉 DB 管理者伺服器...")
        stop_event.set() # 通知背景執行緒停止
        if writer_thread:
            writer_thread.join() # 等待背景執行緒優雅地結束
        log.info("伺服器已完全關閉。")

if __name__ == "__main__":
    run_server()
