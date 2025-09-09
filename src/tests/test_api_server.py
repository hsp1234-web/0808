# src/tests/test_api_server.py

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import os
import json
import sqlite3

# --- 路徑設定 ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

# --- 環境變數設定 ---
os.environ["API_MODE"] = "mock"

# --- 匯入待測目標 ---
from api.api_server import app, UPLOADS_DIR
from db.database import get_db_connection, initialize_database


# --- Pytest Fixtures ---

@pytest.fixture(scope="module")
def client():
    """
    為所有測試提供一個 TestClient 實例。
    """
    initialize_database()

    # 清理 uploads 目錄中的舊檔案
    if UPLOADS_DIR.exists():
        for f in UPLOADS_DIR.glob("*"):
            if f.is_file() and f.name != ".gitkeep":
                f.unlink()

    with TestClient(app) as c:
        yield c


# --- 測試案例 ---

def test_health_check(client: TestClient):
    """
    測試 `/api/health` 端點是否正常運作。
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "API Server is running."}


def test_extract_urls_endpoint(client: TestClient):
    """
    測試 /api/extract_urls 端點的完整流程。
    """
    # --- 準備 ---
    # 1. 清理資料庫中的舊資料
    conn = get_db_connection()
    if not conn:
        pytest.fail("無法建立測試資料庫連線。")

    try:
        with conn:
            # 確保 extracted_urls 資料表存在
            conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                source_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.execute("DELETE FROM extracted_urls")
    finally:
        conn.close()

    # 2. 準備測試資料
    test_text = "這是一個測試，包含兩個網址: https://first.com/path 和 http://second.com"
    payload = {"text": test_text}

    # --- 執行 ---
    response = client.post("/api/extract_urls", json=payload)

    # --- 驗證 API 回應 ---
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "網址提取與儲存成功。"
    assert response_data["urls_found_count"] == 2

    # --- 驗證資料庫 ---
    conn = get_db_connection()
    if not conn:
        pytest.fail("無法建立測試資料庫連線以進行驗證。")

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM extracted_urls ORDER BY url")
        rows = cursor.fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert rows[0]["url"] == "http://second.com"
    assert rows[1]["url"] == "https://first.com/path"
