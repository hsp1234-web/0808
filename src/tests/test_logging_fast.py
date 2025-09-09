# tests/test_logging_fast.py
import pytest
import logging
import sqlite3
import time
from pathlib import Path

# 由於我們要測試的目標是日誌處理器本身，我們需要匯入它
from db.log_handler import DatabaseLogHandler

# JULES'S FIX: 全面重構此測試檔案，使其正確、穩定。

@pytest.fixture
def in_memory_db_and_handler():
    """
    一個提供在記憶體中運行的 DatabaseLogHandler 和對應資料庫連線的 fixture。
    這樣可以確保測試和 handler 操作的是同一個記憶體資料庫。
    """
    # JULES'S FIX V2: 要在多執行緒之間共享記憶體資料庫，必須使用 file-based URI
    # 加上 ?cache=shared。這是解決此測試失敗的關鍵。
    db_uri = f"file:{Path(__file__).stem}_{int(time.time_ns())}?mode=memory&cache=shared"
    conn = None
    handler = None
    try:
        # 1. 建立一個到共享記憶體資料庫的連線
        # 我們需要傳入 uri=True 來告訴 sqlite3 這是一個 URI
        conn = sqlite3.connect(db_uri, uri=True, check_same_thread=False)

        # 2. 在該資料庫中建立必要的表格
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT
            )
        """)
        conn.commit()

        # 3. 建立一個 handler，並將其指向同一個共享記憶體資料庫
        handler = DatabaseLogHandler(source='test_source', db_path=db_uri)

        # 4. 使用 yield 將 handler 和連線物件提供給測試函式
        yield handler, conn

    finally:
        # --- Teardown ---
        # 測試結束後，確保關閉 handler 和連線
        if handler:
            handler.close()
        if conn:
            conn.close()


def test_database_log_handler_writes_log_to_in_memory_db(in_memory_db_and_handler):
    """
    測試 DatabaseLogHandler 是否能成功將一條日誌記錄寫入記憶體資料庫。
    """
    # --- 1. 準備 ---
    handler, conn = in_memory_db_and_handler
    cursor = conn.cursor()

    # 獲取一個專用的 logger，並將我們的記憶體 handler 加入其中
    test_logger = logging.getLogger('my_test_logger')
    test_logger.setLevel(logging.INFO)
    # 清除可能由其他測試留下的 handlers
    test_logger.handlers = []
    test_logger.addHandler(handler)
    # 將 propagate 設為 False，避免日誌被傳遞到 root logger，干擾測試結果
    test_logger.propagate = False

    # 定義要記錄的訊息
    test_message = f"log_message_{int(time.time())}"

    # --- 2. 執行 ---
    # 發送一條 INFO 等級的日誌
    test_logger.info(test_message)

    # JULES'S FIX: 呼叫 close() 會等待背景執行緒處理完所有佇列中的日誌，
    # 這比 time.sleep() 更可靠。
    handler.close()

    # --- 3. 驗證 ---
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
