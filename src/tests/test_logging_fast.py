# tests/test_logging_fast.py
import pytest
import logging
import sqlite3
import time
from unittest.mock import patch

# 由於我們要測試的目標是日誌處理器本身，我們需要匯入它
from db.log_handler import DatabaseLogHandler

@pytest.fixture
def in_memory_db_handler(mocker):
    """
    一個提供在記憶體中運行的 DatabaseLogHandler 的 fixture。
    它會 patch DB_FILE 常數，讓 handler 連接到一個記憶體內的 SQLite 資料庫，
    從而實現了完全的測試隔離，無需操作實體檔案。
    """
    # 使用 mocker.patch 來修改 db.log_handler 模組中的 DB_FILE 常數
    mocker.patch('db.log_handler.DB_FILE', ":memory:")

    # 建立一個 handler 實例，並將其 source 設為 'test_source'
    handler = DatabaseLogHandler(source='test_source')

    # 使用 yield 將 handler 提供給測試函式
    yield handler

    # --- Teardown ---
    # 測試結束後，確保關閉 handler 持有的任何連線
    # (儘管在記憶體模式下這不是嚴格必需的，但這是一個好習慣)
    if hasattr(handler.local, 'conn') and handler.local.conn:
        handler.local.conn.close()
        handler.local.conn = None


def test_database_log_handler_writes_log_to_in_memory_db(in_memory_db_handler):
    """
    測試 DatabaseLogHandler 是否能成功將一條日誌記錄寫入記憶體資料庫。
    """
    # --- 1. 準備 ---
    # 獲取一個專用的 logger，並將我們的記憶體 handler 加入其中
    test_logger = logging.getLogger('my_test_logger')
    test_logger.setLevel(logging.INFO)
    # 清除可能由其他測試留下的 handlers
    test_logger.handlers = []
    test_logger.addHandler(in_memory_db_handler)
    # 將 propagate 設為 False，避免日誌被傳遞到 root logger，干擾測試結果
    test_logger.propagate = False

    # 定義要記錄的訊息
    test_message = f"log_message_{int(time.time())}"

    # --- 2. 執行 ---
    # 發送一條 INFO 等級的日誌
    test_logger.info(test_message)

    # --- 3. 驗證 ---
    # 由於 handler 的寫入是同步的，我們可以直接查詢資料庫
    # 再次使用 in_memory_db_handler.get_conn() 來獲取到同一個記憶體資料庫的連線
    conn = in_memory_db_handler.get_conn()
    cursor = conn.cursor()

    # JULES'S FIX: The in-memory database is empty, so we must create the table first.
    cursor.execute("""
        CREATE TABLE system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT
        )
    """)
    # 重新發送日誌，因為在建立表格之前發送的日誌會失敗
    test_logger.info(test_message)
    time.sleep(0.1) # 給予一點緩衝時間

    # 查詢 system_logs 表中是否有我們剛剛發送的日誌
    cursor.execute("SELECT source, level, message FROM system_logs WHERE message LIKE ?", (f"%{test_message}%",))
    logs = cursor.fetchall()

    # 斷言我們只找到一條匹配的日誌
    assert len(logs) == 1, "應在資料庫中找到且僅找到一條匹配的日誌記錄"

    # 斷言日誌的內容是否正確
    log_entry = logs[0]
    log_source, log_level, log_message = log_entry

    # 根據 DatabaseLogHandler 的邏輯，source 應該是 logger 的名稱
    assert log_source == 'my_test_logger'
    assert log_level == 'INFO'
    assert test_message in log_message
