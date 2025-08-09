# db/database.py
import sqlite3
import logging
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- 資料庫路徑設定 ---
DB_FILE = Path(__file__).parent / "queue.db"

def get_db_connection():
    """建立並回傳一個資料庫連線。"""
    try:
        # isolation_level=None 會開啟 autocommit 模式，但我們將手動管理交易
        conn = sqlite3.connect(DB_FILE, timeout=10) # 增加 timeout
        conn.row_factory = sqlite3.Row # 將回傳結果設定為類似 dict 的物件
        return conn
    except sqlite3.Error as e:
        log.error(f"資料庫連線失敗: {e}")
        return None

def initialize_database():
    """
    初始化資料庫。如果 `tasks` 資料表不存在，就建立它。
    """
    log.info(f"正在檢查並初始化資料庫於: {DB_FILE}")
    conn = get_db_connection()
    if not conn:
        log.critical("無法建立資料庫連線，初始化失敗。")
        return

    try:
        with conn: # 使用 with 陳述式來自動管理交易
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    payload TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Add progress column if it doesn't exist (for migration)
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0")
                log.info("欄位 'progress' 已成功新增至 'tasks' 資料表。")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    pass # Column already exists, ignore
                else:
                    raise
            # 建立索引以加速查詢
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON tasks (task_id)")

            # 新增一個觸發器來自動更新 updated_at 時間戳
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_tasks_updated_at
                AFTER UPDATE ON tasks
                FOR EACH ROW
                BEGIN
                    UPDATE tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END;
            """)
        log.info("✅ 資料庫初始化完成。`tasks` 資料表已存在。")
    except sqlite3.Error as e:
        log.error(f"初始化資料庫時發生錯誤: {e}")
    finally:
        if conn:
            conn.close()

# --- 任務佇列核心功能 ---

def add_task(task_id: str, payload: str) -> bool:
    """
    新增一個新任務到佇列中。

    :param task_id: 唯一的任務 ID。
    :param payload: 任務的內容，通常是 JSON 字串。
    :return: 如果成功新增則回傳 True，否則回傳 False。
    """
    sql = "INSERT INTO tasks (task_id, payload, status) VALUES (?, ?, 'pending')"
    conn = get_db_connection()
    if not conn: return False
    log.info(f"DB:{DB_FILE} 準備新增任務: {task_id}")
    try:
        with conn:
            conn.execute(sql, (task_id, payload))
        log.info(f"✅ 已成功新增任務到佇列: {task_id}")
        return True
    except sqlite3.IntegrityError:
        log.warning(f"⚠️ 嘗試新增一個已存在的任務 ID: {task_id}")
        return False
    except sqlite3.Error as e:
        log.error(f"❌ 新增任務 {task_id} 時發生資料庫錯誤: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()

def fetch_and_lock_task() -> dict | None:
    """
    以原子操作獲取一個待處理的任務，並將其狀態更新為 'processing'。
    這是確保多個 worker 不會同時處理同一個任務的關鍵。

    :return: 一個包含任務資訊的字典，如果沒有待處理任務則回傳 None。
    """
    conn = get_db_connection()
    if not conn: return None

    log.debug(f"DB:{DB_FILE} Worker 正在嘗試獲取任務...")
    try:
        # 使用 IMMEDIATE 交易來立即鎖定資料庫以進行寫入
        with conn:
            cursor = conn.cursor()
            # 1. 查詢並鎖定一個待處理的任務
            cursor.execute(
                "SELECT id, task_id, payload FROM tasks WHERE status = 'pending' ORDER BY created_at LIMIT 1"
            )
            task = cursor.fetchone()

            if task:
                # 2. 如果找到任務，立刻更新其狀態
                task_id_to_process = task["id"]
                log.info(f"🔒 找到並鎖定任務 ID: {task['task_id']} (資料庫 id: {task_id_to_process})")
                cursor.execute(
                    "UPDATE tasks SET status = 'processing' WHERE id = ?", (task_id_to_process,)
                )
                return dict(task)
            else:
                # 佇列中沒有待處理的任務
                log.debug("...佇列為空，無待處理任務。")
                return None
    except sqlite3.Error as e:
        log.error(f"❌ 獲取並鎖定任務時發生錯誤: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()


def update_task_progress(task_id: str, progress: int, partial_result: str):
    """
    更新任務的即時進度和部分結果。
    """
    # 將部分結果打包成與最終結果相同的 JSON 結構
    result_payload = json.dumps({"transcript": partial_result})
    sql = "UPDATE tasks SET progress = ?, result = ? WHERE task_id = ?"
    conn = get_db_connection()
    if not conn: return

    try:
        with conn:
            conn.execute(sql, (progress, result_payload, task_id))
        log.debug(f"📈 任務 {task_id} 進度已更新為: {progress}%")
    except sqlite3.Error as e:
        log.error(f"❌ 更新任務 {task_id} 進度時出錯: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def update_task_status(task_id: str, status: str, result: str = None):
    """
    更新一個任務的狀態和結果。

    :param task_id: 要更新的任務 ID。
    :param status: 新的狀態 ('completed', 'failed')。
    :param result: 任務的結果或錯誤訊息。
    """
    sql = "UPDATE tasks SET status = ?, result = ? WHERE task_id = ?"
    conn = get_db_connection()
    if not conn: return

    try:
        with conn:
            conn.execute(sql, (status, result, task_id))
        log.info(f"✅ 任務 {task_id} 狀態已更新為: {status}")
    except sqlite3.Error as e:
        log.error(f"❌ 更新任務 {task_id} 狀態時出錯: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

def get_task_status(task_id: str) -> dict | None:
    """
    根據 task_id 查詢任務的狀態。

    :param task_id: 要查詢的任務 ID。
    :return: 包含任務狀態的字典，或如果找不到則回傳 None。
    """
    sql = "SELECT task_id, status, payload, result, created_at, updated_at FROM tasks WHERE task_id = ?"
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (task_id,))
        task = cursor.fetchone()
        return dict(task) if task else None
    except sqlite3.Error as e:
        log.error(f"❌ 查詢任務 {task_id} 時發生錯誤: {e}", exc_info=True)
        return None
    finally:
        if conn:
            conn.close()

def are_tasks_active() -> bool:
    """
    檢查是否有任何正在處理中 (processing) 或待處理 (pending) 的任務。
    這對於協調器的 IDLE 狀態檢測至關重要。

    :return: 如果有活動中任務則回傳 True，否則回傳 False。
    """
    sql = "SELECT 1 FROM tasks WHERE status IN ('pending', 'processing') LIMIT 1"
    conn = get_db_connection()
    if not conn: return False # 如果無法連線，假設沒有活動任務以避免死鎖

    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        log.error(f"❌ 檢查活動任務時發生錯誤: {e}", exc_info=True)
        return False # 發生錯誤時，同樣回傳 False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # 直接執行此檔案時，會進行初始化
    initialize_database()
