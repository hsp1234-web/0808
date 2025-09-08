# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime
import pytz

# 定義資料庫檔案的路徑
DB_FILE = "poc_tasks.db"
TIMEZONE = pytz.timezone('Asia/Taipei')

def get_db_connection():
    """建立並返回一個資料庫連線。"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """
    初始化資料庫。如果資料表不存在，則建立它。
    """
    # 為了冪等性，即使檔案存在也執行 CREATE TABLE IF NOT EXISTS
    conn = get_db_connection()
    cursor = conn.cursor()

    # 建立 tasks 資料表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        error_message TEXT,
        file_hash TEXT,
        report_path TEXT
    );
    """)

    conn.commit()
    conn.close()
    print("資料庫和 'tasks' 資料表已成功初始化。")

def create_task(task_id: str, url: str, created_at: str) -> None:
    """在資料庫中建立一個新任務。"""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO tasks (task_id, url, status, created_at) VALUES (?, ?, ?, ?)",
        (task_id, url, "pending", created_at),
    )
    conn.commit()
    conn.close()

def update_task_status(task_id: str, status: str, started_at: str = None) -> None:
    """更新任務的狀態，可選擇性地更新開始時間。"""
    conn = get_db_connection()
    if started_at:
        conn.execute(
            "UPDATE tasks SET status = ?, started_at = ? WHERE task_id = ?",
            (status, started_at, task_id),
        )
    else:
        conn.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?", (status, task_id)
        )
    conn.commit()
    conn.close()

def mark_task_as_failed(task_id: str, error_message: str, finished_at: str) -> None:
    """將任務標記為失敗，並記錄錯誤訊息和完成時間。"""
    conn = get_db_connection()
    conn.execute(
        "UPDATE tasks SET status = 'failed', error_message = ?, finished_at = ? WHERE task_id = ?",
        (error_message, finished_at, task_id),
    )
    conn.commit()
    conn.close()

def update_task_file_hash(task_id: str, file_hash: str) -> None:
    """更新任務的檔案雜湊值。"""
    conn = get_db_connection()
    conn.execute(
        "UPDATE tasks SET file_hash = ? WHERE task_id = ?", (file_hash, task_id)
    )
    conn.commit()
    conn.close()

def update_task_on_completion(task_id: str, status: str, finished_at: str, report_path: str = None) -> None:
    """在任務成功完成時更新其狀態。"""
    conn = get_db_connection()
    if report_path:
        conn.execute(
            "UPDATE tasks SET status = ?, finished_at = ?, report_path = ? WHERE task_id = ?",
            (status, finished_at, report_path, task_id),
        )
    else:
         conn.execute(
            "UPDATE tasks SET status = ?, finished_at = ? WHERE task_id = ?",
            (status, finished_at, task_id),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # 當此腳本被直接執行時，進行資料庫初始化
    print("正在初始化資料庫...")
    initialize_database()
    print("\n資料庫初始化完成。")

    # 以下為資料庫操作函式的基本測試
    print("執行基本資料庫操作測試...")
    test_task_id = "test-12345"
    now_iso = datetime.now(TIMEZONE).isoformat()

    try:
        # 清理舊的測試資料
        conn = get_db_connection()
        conn.execute("DELETE FROM tasks WHERE task_id = ?", (test_task_id,))
        conn.commit()
        conn.close()
        print(f"清理舊的測試任務 '{test_task_id}'。")

        # 測試建立任務
        create_task(test_task_id, "http://test.com", now_iso)
        print(f"成功建立任務: {test_task_id}")

        # 驗證建立
        conn = get_db_connection()
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (test_task_id,)).fetchone()
        conn.close()
        assert task is not None
        assert task['status'] == 'pending'
        print(f"驗證成功: 任務狀態為 '{task['status']}'。")

        # 測試更新狀態
        update_task_status(test_task_id, "processing", started_at=now_iso)
        print("成功更新任務狀態為 'processing'。")

        # 驗證更新
        conn = get_db_connection()
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (test_task_id,)).fetchone()
        conn.close()
        assert task['status'] == 'processing'
        print(f"驗證成功: 任務狀態為 '{task['status']}'。")

        print("\n所有資料庫操作測試成功！")

    except Exception as e:
        print(f"\n資料庫操作測試失敗: {e}")
