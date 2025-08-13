# tests/test_downloader.py
import pytest
import subprocess
import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open, call, ANY

# 由於採用了 src-layout 和可編輯安裝模式 (pip install -e .)，
# pytest 會自動將 src 目錄下的模組視為頂層模組。
from api import api_server

# --- 測試設定 ---
TEST_TASK_ID = "test-youtube-task-123"
TEST_URL = "https://www.youtube.com/watch?v=test_video"
MOCK_AUDIO_PATH = "/tmp/mock_audio.mp3"
MOCK_VIDEO_TITLE = "這是一個測試影片標題"

@pytest.fixture
def mock_db_client(mocker):
    """提供一個模擬的 db_client，用於隔離資料庫操作。"""
    # 創建一個 MagicMock 物件來模擬 db.client.get_client() 的回傳值
    client = MagicMock()

    # 模擬 get_task_status 的行為
    fake_task_payload = json.dumps({"url": TEST_URL})
    client.get_task_status.return_value = {
        "task_id": TEST_TASK_ID,
        "type": "youtube_download_only",
        "payload": fake_task_payload,
        "status": "pending"
    }

    # 使用 mocker.patch 來取代 api_server 模組中的 db_client
    mocker.patch('api.api_server.db_client', new=client)
    return client

@pytest.fixture
def mock_subprocess(mocker):
    """提供一個模擬的 subprocess.Popen，用於隔離外部腳本呼叫。"""
    # 模擬 Popen 的回傳物件
    process_mock = MagicMock()

    # 模擬 stdout 的輸出
    # youtube_downloader.py 腳本在成功時會輸出一個 JSON 結果
    download_result_json = json.dumps({
        "type": "result",
        "status": "completed",
        "output_path": MOCK_AUDIO_PATH,
        "video_title": MOCK_VIDEO_TITLE
    })

    # 模擬 readline() 的行為，就像從子程序的 stdout 讀取一樣
    process_mock.stdout.readline.side_effect = [
        f"{download_result_json}\n",
        ""  # 第二次呼叫回傳空字串，表示串流結束
    ]

    # 模擬 wait() 和 returncode
    process_mock.wait.return_value = None
    process_mock.returncode = 0

    # 使用 mocker.patch 來取代 subprocess.Popen
    popen_mock = mocker.patch('subprocess.Popen', return_value=process_mock)
    return popen_mock

@pytest.fixture
def mock_websocket_manager(mocker):
    """提供一個模擬的 WebSocket 管理器和廣播功能。"""
    # 模擬 ConnectionManager
    manager_mock = MagicMock()

    # 我們仍然需要 patch asyncio.run_coroutine_threadsafe，因為它會被呼叫，
    # 但我們不再需要檢查它的呼叫，而是檢查 manager_mock 的方法呼叫。
    mocker.patch('api.api_server.asyncio.run_coroutine_threadsafe')

    # 將模擬的 manager patch 到 api_server 模組中
    mocker.patch('api.api_server.manager', new=manager_mock)

    # 回傳 manager_mock 以便在測試中進行斷言
    return manager_mock

def test_trigger_youtube_processing_success(mock_db_client, mock_subprocess, mock_websocket_manager):
    """
    測試 trigger_youtube_processing 函式在 'youtube_download_only' 模式下
    成功執行的完整流程。
    """
    # --- 1. 準備 ---
    # 建立一個假的 asyncio 事件迴圈物件，因為函式需要它
    mock_loop = MagicMock()

    # --- 2. 執行 ---
    # 呼叫我們要測試的目標函式
    # 由於它會在一個新執行緒中執行 `_process_in_thread`，我們需要確保測試能夠等待它完成。
    # 在這個測試設定中，由於 Popen 是被模擬的，它會立即返回，所以執行緒會很快完成。
    api_server.trigger_youtube_processing(TEST_TASK_ID, mock_loop)

    # 為了確保執行緒有足夠的時間執行，我們可以加入一個短暫的等待
    import time
    time.sleep(0.1)

    # --- 3. 斷言 ---
    # 斷言資料庫狀態的更新
    mock_db_client.get_task_status.assert_called_once_with(TEST_TASK_ID)

    # 斷言子程序被正確呼叫
    # JULES'S FIX (2025-08-12): 修正因 src-layout 重構導致的路徑問題
    # api_server.py 現在使用 ROOT_DIR 來建構絕對路徑
    tool_name = "mock_youtube_downloader.py" if api_server.IS_MOCK_MODE else "youtube_downloader.py"
    expected_tool_path = api_server.ROOT_DIR / "src" / "tools" / tool_name

    expected_cmd = [
        sys.executable,
        str(expected_tool_path),
        "--url", TEST_URL,
        "--output-dir", str(api_server.UPLOADS_DIR),
        "--download-type", "audio"  # JULES: 修正測試案例，使其與 api_server 的實際呼叫保持一致
    ]
    mock_subprocess.assert_called_once_with(
        expected_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        env=ANY # JULES'S FIX (2025-08-12): 確保測試能處理 env 參數
    )

    # 斷言 WebSocket 廣播的訊息
    # 我們預期有兩次廣播：一次是 'downloading'，一次是 'completed'
    final_download_result = {
        "type": "result",
        "status": "completed",
        "output_path": MOCK_AUDIO_PATH,
        "video_title": MOCK_VIDEO_TITLE
    }

    expected_calls = [
        # 第一次呼叫：狀態變為 'downloading'
        call({
            "type": "YOUTUBE_STATUS",
            "payload": {
                "task_id": TEST_TASK_ID,
                "status": "downloading",
                    "message": f"正在下載 (audio): {TEST_URL}", # JULES: 修正測試案例，使其與 api_server 的實際廣播訊息一致
                "task_type": "youtube_download_only"
            }
        }),
        # 第二次呼叫：狀態變為 'completed'
        call({
            "type": "YOUTUBE_STATUS",
            "payload": {
                "task_id": TEST_TASK_ID,
                "status": "completed",
                "result": final_download_result,
                "task_type": "download_only"
            }
        })
    ]
    # 現在我們斷言 manager.broadcast_json 被呼叫
    mock_websocket_manager.broadcast_json.assert_has_calls(expected_calls, any_order=False)

    # 斷言資料庫任務狀態最終被更新為 'completed'
    final_db_update_call = call(TEST_TASK_ID, 'completed', json.dumps(final_download_result))
    mock_db_client.update_task_status.assert_has_calls([final_db_update_call])

def test_mock_youtube_downloader_script(tmp_path):
    """
    直接測試 mock_youtube_downloader.py 腳本的行為。

    這個測試驗證該腳本是否：
    1. 成功執行並回傳退出碼 0。
    2. 在 stdout 輸出一行有效的 JSON 結果。
    3. JSON 結果中包含一個指向實際建立的檔案的 'output_path'。
    4. 建立的檔案內容符合預期。
    """
    # --- 1. 準備 ---
    test_url = "https://www.youtube.com/watch?v=mock_video_for_unit_test"
    output_dir = tmp_path
    tool_path = api_server.ROOT_DIR / "src" / "tools" / "mock_youtube_downloader.py"

    cmd = [
        sys.executable,
        str(tool_path),
        "--url", test_url,
        "--output-dir", str(output_dir)
    ]

    # --- 2. 執行 ---
    # 使用 subprocess.run 來執行腳本並等待其完成
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

    # --- 3. 斷言 ---
    # 斷言腳本成功執行
    assert result.returncode == 0, f"腳本執行失敗，stderr: {result.stderr}"

    # 斷言 stdout 不是空的
    assert result.stdout, "腳本沒有任何輸出到 stdout"

    # 解析最後一行輸出，因為進度更新會輸出到 stderr
    lines = result.stdout.strip().splitlines()
    assert len(lines) > 0, "stdout 中沒有有效的輸出行"
    last_line = lines[-1]

    try:
        output_json = json.loads(last_line)
    except json.JSONDecodeError:
        pytest.fail(f"無法將 stdout 的最後一行解析為 JSON: '{last_line}'")

    # 斷言 JSON 內容
    assert output_json.get("type") == "result"
    assert output_json.get("status") == "completed"
    assert "output_path" in output_json
    assert "video_title" in output_json

    # 斷言檔案確實被建立
    output_path_str = output_json["output_path"]
    assert isinstance(output_path_str, str)
    assert output_path_str.endswith(".mp3")

    output_path = Path(output_path_str)
    assert output_path.exists(), f"腳本回報的路徑不存在: {output_path_str}"
    assert output_path.is_file()

    # 斷言檔案內容
    content = output_path.read_text(encoding='utf-8')
    # JULES'S FIX: 使用 .strip() 來移除潛在的尾隨換行符，使斷言更可靠
    assert content.strip() == "這是一個模擬的音訊檔案。"
