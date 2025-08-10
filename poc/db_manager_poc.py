# poc/db_manager_poc.py
import multiprocessing
import sqlite3
import time
import logging
from pathlib import Path
import os

# --- 基本設定 ---
LOG_FORMAT = '%(asctime)s - %(processName)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

POC_DIR = Path(__file__).parent
DB_FILE = POC_DIR / "poc_queue.db"

# --- 資料庫管理者程序 ---

def initialize_database(db_path):
    """(僅由管理者程序呼叫) 初始化資料庫和資料表。"""
    logging.info(f"初始化資料庫於 {db_path}...")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS poc_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logging.info("資料庫初始化完成。")
    except sqlite3.Error as e:
        logging.error(f"資料庫初始化失敗: {e}", exc_info=True)
        raise

def db_manager(queue: multiprocessing.Queue, db_path: Path):
    """
    此程序是唯一與資料庫檔案互動的實體。
    它從佇列接收指令並執行。
    """
    logging.info("資料庫管理者已啟動。")

    # 在開始監聽前，先初始化資料庫
    initialize_database(db_path)

    conn = sqlite3.connect(db_path, timeout=10)

    while True:
        try:
            command = queue.get()
            if command is None: # 收到關閉信號
                logging.info("收到關閉信號，正在關閉...")
                break

            action = command.get("action")

            if action == "add":
                data = command.get("data")
                client_name = command.get("client_name")
                logging.info(f"正在處理來自 '{client_name}' 的 'add' 指令...")
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO poc_tasks (client_name, data) VALUES (?, ?)",
                    (client_name, data)
                )
                conn.commit()
                logging.info(f"✅ 已成功為 '{client_name}' 新增資料。")

            # 可以在此處擴展其他指令，例如 'get', 'update' 等

        except Exception as e:
            logging.error(f"處理指令時發生錯誤: {e}", exc_info=True)

    conn.close()
    logging.info("資料庫管理者已關閉。")


# --- 客戶端程序 ---

def client(queue: multiprocessing.Queue, client_name: str, num_tasks: int):
    """
    此程序模擬一個需要存取資料庫的應用程式。
    它將指令放入佇列，而不是直接存取資料庫。
    """
    logging.info(f"客戶端 '{client_name}' 已啟動。")
    for i in range(num_tasks):
        task_data = f"任務 {i+1} from {client_name}"
        command = {
            "action": "add",
            "client_name": client_name,
            "data": task_data
        }
        queue.put(command)
        logging.info(f"'{client_name}' 已發送指令: {command}")
        time.sleep(0.05) # 模擬一些工作負載
    logging.info(f"客戶端 '{client_name}' 已完成所有任務。")


# --- 主執行區塊 ---

if __name__ == "__main__":
    logging.info("--- 概念驗證 (POC) 啟動 ---")

    # 1. 在每次執行前，先清理舊的資料庫檔案
    # 這是為了模擬 local_run.py 的行為
    if DB_FILE.exists():
        logging.info(f"正在清理舊的資料庫檔案: {DB_FILE}")
        DB_FILE.unlink()
        logging.info("✅ 舊資料庫已刪除。")

    # 2. 建立通訊佇列
    task_queue = multiprocessing.Queue()

    # 3. 建立並啟動管理者和客戶端程序
    processes = []

    # 建立管理者
    manager_process = multiprocessing.Process(
        target=db_manager,
        args=(task_queue, DB_FILE),
        name="DBManager"
    )
    processes.append(manager_process)

    # 建立客戶端
    client1 = multiprocessing.Process(
        target=client,
        args=(task_queue, "Client-1", 3),
        name="Client-1"
    )
    processes.append(client1)

    client2 = multiprocessing.Process(
        target=client,
        args=(task_queue, "Client-2", 2),
        name="Client-2"
    )
    processes.append(client2)

    # 依序啟動所有程序
    for p in processes:
        p.start()
        # 在啟動管理者後短暫延遲，確保它有足夠時間建立資料庫
        # 這模仿了真實世界中服務啟動需要時間的情況
        if p.name == "DBManager":
             time.sleep(0.2)

    # 4. 等待客戶端完成工作
    logging.info("主程序：等待所有客戶端完成...")
    client1.join()
    client2.join()
    logging.info("✅ 所有客戶端均已完成。")

    # 5. 發送關閉信號給管理者
    logging.info("主程序：正在發送關閉信號給管理者...")
    task_queue.put(None)

    # 6. 等待管理者關閉
    manager_process.join()
    logging.info("✅ 管理者已關閉。")

    # 7. 最終驗證
    logging.info("--- 最終驗證 ---")
    if not DB_FILE.exists():
        logging.error("❌ 驗證失敗：資料庫檔案不存在！")
    else:
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM poc_tasks")
                count = cursor.fetchone()[0]
                logging.info(f"在資料庫中找到 {count} 筆紀錄。")

                # 預期 Client-1 新增 3 筆，Client-2 新增 2 筆
                expected_count = 5
                if count == expected_count:
                    logging.info(f"✅ 驗證成功！紀錄數量 ({count}) 符合預期 ({expected_count})。")
                else:
                    logging.error(f"❌ 驗證失敗！紀錄數量 ({count}) 不符合預期 ({expected_count})。")
        except Exception as e:
            logging.error(f"❌ 驗證過程中發生錯誤: {e}")

    logging.info("--- 概念驗證 (POC) 結束 ---")
