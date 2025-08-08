# -*- coding: utf-8 -*-
# 檔名: tools/heartbeat_probe.py
# 說明: 一個獨立、最小化的探測器腳本，用於驗證核心的 asyncio 背景任務功能。

import asyncio
import sqlite3
import os
import threading
from datetime import datetime, timezone

DB_PATH = "probe_test.db"
HEARTBEAT_KEY = "probe_heartbeat"

def initialize_database():
    """建立並初始化一個乾淨的資料庫。"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    print(f"[{datetime.now()}] [MAIN] 正在初始化資料庫於 {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS status_updates (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()
    print(f"[{datetime.now()}] [MAIN] 資料庫初始化完成。")

async def periodic_heartbeat_writer(interval_seconds: int):
    """一個極簡的心跳寫入器。"""
    print(f"[{datetime.now()}] [HEARTBEAT_TASK] 心跳任務已啟動。")
    # 注意：在真實的多執行緒應用中，為每個執行緒建立一個新的 connection
    # 或是使用一個執行緒安全的佇列是更好的做法。
    # 為了簡單起見，我們在這裡為此任務建立一個獨立的連線。
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    while True:
        try:
            current_time_str = datetime.now(timezone.utc).isoformat()

            # 直接執行阻塞的 I/O
            conn.execute(
                "INSERT INTO status_updates (key, value, timestamp) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, timestamp=excluded.timestamp",
                (HEARTBEAT_KEY, current_time_str, current_time_str)
            )
            conn.commit()
            print(f"[{datetime.now()}] [HEARTBEAT_TASK] ✅ PING! 心跳已寫入。")

        except Exception as e:
            print(f"[{datetime.now()}] [HEARTBEAT_TASK] ❌ 錯誤: {e}")

        await asyncio.sleep(interval_seconds)

async def main():
    """主執行函式。"""
    initialize_database()

    print(f"[{datetime.now()}] [MAIN] 正在創建心跳任務...")
    heartbeat_task = asyncio.create_task(periodic_heartbeat_writer(interval_seconds=1))

    # 讓腳本運行 5 秒鐘
    print(f"[{datetime.now()}] [MAIN] 探測器將運行 5 秒鐘...")
    await asyncio.sleep(5)

    # 停止任務
    print(f"[{datetime.now()}] [MAIN] 正在停止心跳任務...")
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        print(f"[{datetime.now()}] [MAIN] 任務已成功取消。")

    # 最後驗證資料庫中的值
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM status_updates WHERE key = ?", (HEARTBEAT_KEY,))
    result = cursor.fetchone()
    conn.close()

    print("\n--- 最終驗證 ---")
    if result:
        print(f"✅ 成功：在資料庫中找到最終心跳: {result[0]}")
    else:
        print("❌ 失敗：無法在資料庫中找到心跳記錄。")

    os.remove(DB_PATH)
    print(f"清理完成，已刪除 {DB_PATH}。")

if __name__ == "__main__":
    asyncio.run(main())
