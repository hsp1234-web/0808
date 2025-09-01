import pytest
import logging
import sqlite3
import time
from unittest.mock import patch

from db.log_handler import DatabaseLogHandler, DB_FILE as ACTUAL_DB_FILE

# Define the schema creation SQL
CREATE_TABLE_SQL = """
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT
)
"""

@pytest.fixture
def in_memory_db_and_handler(mocker):
    """
    A fixture that provides a fully isolated, in-memory DatabaseLogHandler.

    It patches the DB_FILE constant to use a shared in-memory database,
    creates the necessary table, and provides both the handler and a direct
    connection for verification.
    """
    # Use a shareable in-memory database URI. This allows multiple
    # connections (from the handler thread and the test) to access the SAME db.
    in_memory_db_uri = "file::memory:?cache=shared"
    mocker.patch('db.log_handler.DB_FILE', in_memory_db_uri)

    # Establish a separate connection for setup and verification
    verification_conn = sqlite3.connect(in_memory_db_uri, uri=True)
    cursor = verification_conn.cursor()

    # Create the table required by the handler
    cursor.execute(CREATE_TABLE_SQL)
    verification_conn.commit()

    # Create the handler instance which will now connect to the same in-memory db
    handler = DatabaseLogHandler(source='test_fixture')

    # Yield both the handler and the verification connection to the test
    yield handler, verification_conn

    # --- Teardown ---
    handler.close()  # Gracefully shutdown the handler's writer thread
    verification_conn.close() # Close our verification connection

def test_database_log_handler_writes_log_to_in_memory_db(in_memory_db_and_handler):
    """
    Tests if the DatabaseLogHandler can successfully write a log record to
    the in-memory database.
    """
    # --- 1. Arrange ---
    handler, verification_conn = in_memory_db_and_handler
    cursor = verification_conn.cursor()

    test_logger = logging.getLogger('my_test_logger')
    test_logger.setLevel(logging.INFO)
    test_logger.handlers = []
    test_logger.addHandler(handler)
    test_logger.propagate = False

    test_message = f"log_message_{int(time.time())}"

    # --- 2. Act ---
    # Emit a log message. It gets put into the handler's queue.
    test_logger.info(test_message)

    # Crucially, we must close the handler to ensure the background thread
    # processes the queue and writes to the database before we verify.
    handler.close()

    # --- 3. Assert ---
    # Now that the handler is closed, the log should be in the database.
    # We use our separate verification connection to check.
    cursor.execute("SELECT source, level, message FROM system_logs WHERE message LIKE ?", (f"%{test_message}%",))
    logs = cursor.fetchall()

    assert len(logs) == 1, "Should find exactly one matching log record in the database"

    log_source, log_level, log_message = logs[0]

    assert log_source == 'my_test_logger'
    assert log_level == 'INFO'
    assert test_message in log_message
