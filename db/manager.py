# db/manager.py
import socketserver
import json
import logging
import sqlite3
from pathlib import Path

# 讓此腳本可以存取上層目錄的 db.database 模組
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db import database

# --- 日誌設定 ---
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger('DBManagerServer')

# --- 伺服器設定 ---
HOST, PORT = "127.0.0.1", 49999 # JULES: Hardcoded port to fix race condition

# --- 指令分派 ---
# 建立一個函式名稱與指令 action 的對應字典
# 這樣可以避免巨大的 if/elif/else 結構，也更安全
ACTION_MAP = {
    "initialize_database": database.initialize_database,
    "add_task": database.add_task,
    "fetch_and_lock_task": database.fetch_and_lock_task,
    "update_task_progress": database.update_task_progress,
    "update_task_status": database.update_task_status,
    "get_task_status": database.get_task_status,
    "are_tasks_active": database.are_tasks_active,
    "get_all_tasks": database.get_all_tasks,
    "get_system_logs": database.get_system_logs_by_filter,
}


class DBRequestHandler(socketserver.BaseRequestHandler):
    """
    處理來自客戶端請求的處理器。
    每個連線都會建立一個此類別的實例。
    """
    def handle(self):
        log.info(f"來自 {self.client_address} 的新連線。")
        try:
            while True:
                # 接收資料的長度 (4-byte header)
                header = self.request.recv(4)
                if not header:
                    break # 連線已關閉

                data_len = int.from_bytes(header, 'big')

                # 根據長度接收完整的資料
                data = self.request.recv(data_len)
                if not data:
                    break

                request = json.loads(data.decode('utf-8'))
                log.info(f"收到請求: {request}")

                action = request.get("action")
                params = request.get("params", {})

                response = {}
                try:
                    if action in ACTION_MAP:
                        # 從字典中獲取對應的函式
                        func = ACTION_MAP[action]

                        # 呼叫函式並傳入參數
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
                    # 將例外轉為字串，以便序列化
                    response["message"] = f"執行 '{action}' 時發生內部錯誤: {str(e)}"

                # 將回應序列化並發送回客戶端
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
    啟動資料庫管理者伺服器。
    """
    # 在伺服器啟動前，先主動清理任何可能存在的舊 port 檔案，確保一致性
    port_file = Path(__file__).parent / "db_manager.port"
    if port_file.exists():
        try:
            port_file.unlink()
            log.info(f"已成功移除舊的埠號檔案: {port_file}")
        except OSError as e:
            # 即便移除失敗，也只記錄錯誤，不中斷啟動流程
            log.error(f"無法移除舊的埠號檔案: {e}", exc_info=True)

    # 這是整個系統中，唯一應該呼叫 `initialize_database` 的地方
    try:
        log.info("資料庫管理者伺服器啟動前，正在進行資料庫初始化...")
        database.initialize_database()
        log.info("✅ 資料庫初始化成功。")
    except sqlite3.Error as e:
        log.critical(f"❌ 資料庫初始化失敗，伺服器無法啟動: {e}")
        # 在這種嚴重錯誤下，我們應該讓程序以非零代碼退出
        sys.exit(1)

    # 建立 TCP 伺服器
    # 讓 server 在程式結束後可以立即重用同一個位址
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((HOST, PORT), DBRequestHandler) as server:
        # 獲取實際綁定的埠號
        actual_port = server.server_address[1]
        log.info(f"🚀 資料庫管理者伺服器已在 {HOST}:{actual_port} 上啟動...")

        try:
            # 啟動伺服器，它將一直運行直到被中斷 (例如 Ctrl+C)
            server.serve_forever()
        finally:
            log.info("伺服器已關閉。")


if __name__ == "__main__":
    run_server()
