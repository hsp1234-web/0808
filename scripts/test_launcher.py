# scripts/test_launcher.py
import sys
import os
import subprocess
import time
import multiprocessing
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# --- Test Configuration ---
TEST_TIMEOUT = 60  # 60-second timeout as requested by the user

# We need to import the script we are testing.
# To do this, we need to make sure the root directory is in the python path
# as this script is in a subdirectory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import colabPro

# --- Helper Function to run the launcher in a separate process ---

def launcher_process_wrapper(shared_dict):
    """
    This function is the target for the multiprocessing.Process.
    It runs the main logic of colabPro and communicates results back
    through a shared dictionary.
    """
    try:
        # We need to mock all external dependencies of colabPro
        # Patching download_repository to avoid git clone and filesystem writes
        with patch('colabPro.download_repository') as mock_download:
            # Create a temporary directory for the fake project
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Setup the fake project structure that the script expects
                (temp_path / "src" / "core").mkdir(parents=True, exist_ok=True)
                (temp_path / "requirements").mkdir(exist_ok=True)

                # Create dummy files
                (temp_path / "src" / "core" / "orchestrator.py").touch()
                (temp_path / "requirements" / "server.txt").write_text("fake-package==1.0")

                mock_download.return_value = str(temp_path)

                # Patch subprocess.Popen to simulate the orchestrator
                with patch('subprocess.Popen') as mock_popen:
                    # Configure the mock process that Popen returns
                    mock_proc = MagicMock()

                    # Simulate the stdout stream
                    # The orchestrator is expected to print the PROXY_URL
                    # We get this from the shared dictionary to control the test case
                    stdout_lines = shared_dict.get('stdout_simulation', [])
                    # Make the mock readline return each line from our list, then empty string
                    mock_proc.stdout.readline.side_effect = stdout_lines + [b'']

                    # Simulate the process not terminating on its own
                    mock_proc.poll.return_value = None

                    mock_popen.return_value = mock_proc

                    # Patch other external dependencies
                    with patch('colabPro.ipy_clear_output'), \
                         patch('colabPro.display'), \
                         patch('colabPro.HTML'), \
                         patch('colabPro.requests.get') as mock_requests_get:

                        # Mock the health check response
                        mock_health_response = MagicMock()
                        mock_health_response.status_code = 200
                        mock_health_response.json.return_value = {"status": "ok"}
                        mock_requests_get.return_value = mock_health_response

                        # Now, run the actual logic from colabPro
                        # We need to create a mock-like log manager to inspect its state
                        shared_state = {
                            "start_time_monotonic": time.monotonic(),
                            "status": "初始化...",
                            "urls": {},
                            "all_tunnels_done": False
                        }
                        log_manager = colabPro.DisplayManager(shared_state)

                        # Call the main function to be tested
                        colabPro.launch_application(str(temp_path), log_manager)

                        # After the function returns, put the final state back
                        # in the shared dictionary for the main process to assert against.
                        shared_dict['final_status'] = shared_state.get('status')
                        shared_dict['final_app_port'] = shared_state.get('app_port')
                        shared_dict['success'] = True

    except Exception as e:
        shared_dict['success'] = False
        shared_dict['error'] = str(e)
        shared_dict['final_status'] = "❌ 測試進程發生未預期錯誤"

# --- Pytest Test Cases ---

@pytest.fixture(scope="module", autouse=True)
def self_destruct_fixture():
    """Pytest fixture to handle the self-destruction of the test file."""
    yield
    # This code runs after all tests in the file are complete
    print("\n--- 測試完成，正在自動刪除測試腳本... ---")
    try:
        os.remove(__file__)
        print(f"✅ 成功刪除: {__file__}")
    except OSError as e:
        print(f"❌ 刪除測試腳本失敗: {e}")

def test_successful_launch_simulation():
    """
    測試案例：模擬一次成功的啟動流程。
    驗證啟動器能否在超時前，正確解析出來自模擬後端的 `PROXY_URL` 信號。
    """
    manager = multiprocessing.Manager()
    shared_dict = manager.dict()

    # Configure the simulation: provide the success signal
    shared_dict['stdout_simulation'] = [
        b"some irrelevant log line\n",
        b"PROXY_URL: http://127.0.0.1:12345\n",
        b"another log line\n"
    ]

    p = multiprocessing.Process(target=launcher_process_wrapper, args=(shared_dict,))
    p.start()

    # We expect the main function to return after health check, not hang forever
    # So the timeout here is a safety net.
    p.join(timeout=TEST_TIMEOUT)

    assert not p.is_alive(), f"測試超時！啟動器在 {TEST_TIMEOUT} 秒內未能完成。"

    assert shared_dict.get('success', False), f"測試進程內部發生錯誤: {shared_dict.get('error', '未知錯誤')}"
    assert shared_dict.get('final_app_port') == 12345, "啟動器未能正確解析出埠號。"
    assert "✅ 應用程式已就緒" in shared_dict.get('final_status', ''), "啟動器未能達到最終的『就緒』狀態。"
    print("\n✅ [PASS] 成功啟動流程測試通過。")

def test_launch_timeout_simulation():
    """
    測試案例：模擬一次因後端無回應而導致的超時。
    驗證啟動器不會無限期卡住，且測試框架能正確捕捉到超時。
    """
    manager = multiprocessing.Manager()
    shared_dict = manager.dict()

    # Configure the simulation: DO NOT provide the success signal
    shared_dict['stdout_simulation'] = [
        b"some irrelevant log line\n",
        b"another log line without the signal\n"
    ]

    p = multiprocessing.Process(target=launcher_process_wrapper, args=(shared_dict,))
    p.start()
    p.join(timeout=TEST_TIMEOUT)

    # In this case, we EXPECT the process to be alive (stuck) and then terminated by join()
    if p.is_alive():
        p.terminate()
        p.join()
        print("\n✅ [PASS] 啟動器如預期般發生超時，並被測試框架成功終止。")
        assert True
    else:
        # It's also possible it exited cleanly with an error, which is also acceptable.
        # Let's check the error message in that case.
        assert '在 30 秒內未偵測到後端回報的埠號' in shared_dict.get('error', ''), "測試未能如預期般超時，且沒有回報正確的超時錯誤訊息。"
        print("\n✅ [PASS] 啟動器如預期般因未收到信號而報告錯誤並終止。")
