# tests/test_worker.py
import pytest
import json
import subprocess
from unittest.mock import MagicMock, patch, call, ANY

# 由於採用了 src-layout 和可編輯安裝模式 (pip install -e .)，
# pytest 會自動將 src 目錄下的模組視為頂層模組。
from tasks import worker

# --- 測試資料 ---
TEST_TASK_ID = "test-transcribe-task-456"
MOCK_AUDIO_FILE = "/path/to/mock_audio.wav"

@pytest.fixture
def mock_db_client(mocker):
    """提供一個模擬的 db_client，用於隔離資料庫操作。"""
    client = MagicMock()

    # 模擬 fetch_and_lock_task 的行為
    # 第一次呼叫回傳一個任務，第二次呼叫回傳 None 以便迴圈結束
    mock_task_payload = json.dumps({
        "input_file": MOCK_AUDIO_FILE,
        "model_size": "tiny",
        "language": "en"
    })
    mock_task = {
        "task_id": TEST_TASK_ID,
        "payload": mock_task_payload,
        "type": "transcribe"
    }
    client.fetch_and_lock_task.side_effect = [mock_task, None]

    # 使用 mocker.patch 來取代 worker 模組中的 db_client
    mocker.patch('tasks.worker.db_client', new=client)
    return client

@pytest.fixture
def mock_subprocess(mocker):
    """提供一個模擬的 subprocess.Popen，用於隔離外部腳本呼叫。"""
    process_mock = MagicMock()
    # 模擬 stdout 的輸出 (來自 mock_transcriber.py 的假輸出)
    mock_output_line = json.dumps({
        "type": "segment", "start": 0, "end": 2, "text": "這是模擬的轉錄文字。"
    })
    process_mock.stdout.readline.side_effect = [f"{mock_output_line}\n", ""]
    process_mock.wait.return_value = None
    process_mock.returncode = 0
    # 我們需要一個假的 stderr，即使它是空的
    process_mock.stderr.readline.side_effect = [""]


    popen_mock = mocker.patch('subprocess.Popen', return_value=process_mock)
    return popen_mock

@pytest.fixture
def mock_requests(mocker):
    """提供一個模擬的 requests.post，用於隔離對 API server 的通知。"""
    post_mock = mocker.patch('requests.post')
    return post_mock

@pytest.fixture
def mock_file_io(mocker):
    """模擬檔案系統操作，例如 Path.exists 和 read_text。"""
    # 模擬 input_file.exists()
    mocker.patch('pathlib.Path.exists', return_value=True)
    # 模擬 output_file.read_text()
    mocker.patch('pathlib.Path.read_text', return_value="這是模擬的轉錄文字。")
    # 模擬 mkdir
    mocker.patch('pathlib.Path.mkdir')


def test_worker_main_loop_full_workflow(
    mock_db_client, mock_subprocess, mock_requests, mock_file_io
):
    """
    測試 worker 的 main_loop 在一個完整的轉錄任務流程中的行為。
    """
    # --- 1. 執行 ---
    # 呼叫主迴圈。因為 fetch_and_lock_task 被 mock 成第二次回傳 None，
    # 這個迴圈只會執行一次，然後就會退出。
    # 我們也傳遞一個非常短的輪詢間隔，以加速測試。
    worker.main_loop(use_mock=True, poll_interval=0.01)

    # --- 2. 斷言 ---
    # 2a. 斷言資料庫互動
    # 檢查是否嘗試獲取任務
    mock_db_client.fetch_and_lock_task.assert_called()
    # 檢查任務狀態是否被更新為 'completed'
    # 我們需要檢查最後一次呼叫，因為可能會有進度更新
    final_status_call = mock_db_client.update_task_status.call_args
    assert final_status_call.args[0] == TEST_TASK_ID
    assert final_status_call.args[1] == 'completed'
    # 檢查結果是否包含正確的 transcript
    result_json = json.loads(final_status_call.args[2])
    assert result_json['transcript'] == "這是模擬的轉錄文字。"

    # 2b. 斷言子程序呼叫
    # 檢查是否正確地呼叫了 mock_transcriber.py
    call_args, call_kwargs = mock_subprocess.call_args
    command_list = call_args[0]
    assert "mock_transcriber.py" in command_list[1]
    # JULES'S FIX: The order of arguments is not guaranteed, so check for presence instead of index.
    assert any(arg.startswith('--audio_file=') for arg in command_list)
    assert any(arg.startswith('--output_file=') for arg in command_list)

    # 2c. 斷言 API 通知
    # 檢查是否向 API server 發送了 POST 請求
    mock_requests.assert_called_once()
    # 檢查請求的 URL 和 payload
    request_args, request_kwargs = mock_requests.call_args
    assert request_args[0] == "http://127.0.0.1:42649/api/internal/notify_task_update"
    sent_payload = request_kwargs['json']
    assert sent_payload['task_id'] == TEST_TASK_ID
    assert sent_payload['status'] == 'completed'
    assert sent_payload['result']['transcript'] == "這是模擬的轉錄文字。"
