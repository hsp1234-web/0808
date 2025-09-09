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
# HACK: 但是在某些 CI/CD 環境中，PYTHONPATH 可能沒有被正確設定。
#       為了確保測試的穩定性，我們手動將 'src' 目錄加到系統路徑中。
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import api_server

# --- 測試設定 ---
TEST_TASK_ID = "test-youtube-task-123"
TEST_URL = "https://www.youtube.com/watch?v=test_video"
MOCK_AUDIO_PATH = "/tmp/mock_audio.mp3"
MOCK_VIDEO_TITLE = "這是一個測試影片標題"


@pytest.fixture
def mock_subprocess(mocker):
    """提供一個模擬的 subprocess.Popen，用於隔離外部腳本呼叫。"""
    # 模擬 Popen 的回傳物件
    process_mock = MagicMock()

    # 模擬 stdout 的輸出
    # youtube_downloader.py 腳本在成功時會輸出一個 JSON 結果
    download_result_json = json.dumps({
        "type": "result",
        "status": "已完成",
        "output_path": MOCK_AUDIO_PATH,
        "video_title": MOCK_VIDEO_TITLE
    })

    # 模擬 communicate() 的行為，它會回傳 (stdout, stderr)
    process_mock.communicate.return_value = (download_result_json, "")

    # 模擬 wait() 和 returncode
    process_mock.wait.return_value = None
    process_mock.returncode = 0

    # 使用 mocker.patch 來取代 subprocess.Popen
    popen_mock = mocker.patch('subprocess.Popen', return_value=process_mock)
    return popen_mock


# JULES'S NOTE: The test `test_trigger_youtube_processing_success` was here.
# It was removed because it was an integration test for the old WebSocket-based
# orchestrator logic which has been replaced by the new SSE architecture.

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
    assert result.returncode == 0, f"腳本執行失敗，stdout: {result.stdout}, stderr: {result.stderr}"

    # 斷言 stdout (標準輸出) 只包含最終的結果 JSON
    assert result.stdout, "腳本沒有任何輸出到 stdout"
    try:
        # stdout 應該只包含一個 JSON 物件
        output_json = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"無法將 stdout 的內容解析為一個單一的 JSON 物件: '{result.stdout}'")

    # 斷言 stderr (標準錯誤) 包含進度更新
    assert result.stderr, "腳本沒有任何進度更新輸出到 stderr"
    progress_lines = result.stderr.strip().splitlines()
    assert len(progress_lines) > 2, "預期至少有3行進度更新"
    for line in progress_lines:
        try:
            progress_json = json.loads(line)
            assert progress_json.get("type") == "progress", f"stderr 中的行不是 'progress' 類型: {line}"
            assert "percent" in progress_json, f"stderr 中的進度更新缺少 'percent' 鍵: {line}"
        except json.JSONDecodeError:
            pytest.fail(f"無法將 stderr 的某一行解析為 JSON: '{line}'")


    # 斷言 JSON 內容
    assert output_json.get("type") == "result"
    assert output_json.get("status") == "已完成"
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


# ==================================================================
# ===== 新增針對 src/tools/downloader.py 模組的單元測試 =====
# ==================================================================

# 為了避免與上面的整合測試衝突，我們需要重新匯入新的 downloader 模組
# 並且在測試中使用它
from tools import downloader

@pytest.fixture
def mock_subprocess_run(mocker):
    """模擬 subprocess.run 函式。"""
    return mocker.patch('subprocess.run')

@pytest.fixture
def mock_path_exists(mocker):
    """模擬 Path.exists() 方法。"""
    return mocker.patch('pathlib.Path.exists', return_value=True)

@pytest.mark.parametrize("download_type, expected_suffix", [("audio", ".mp3"), ("video", ".mp4")])
def test_download_media_success(
    mock_subprocess_run,
    mock_path_exists,
    tmp_path,
    download_type,
    expected_suffix
):
    """
    測試 download_media 函式在成功情境下的行為 (音訊和影片)。
    """
    # --- 準備 ---
    url = "http://fake.youtube.com/watch?v=123"
    output_dir = tmp_path
    mock_video_title = "測試標題"
    expected_output_path = output_dir / f"{mock_video_title}{expected_suffix}"

    # 設定模擬的 subprocess.run 的回傳值
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({
        "_filename": str(expected_output_path),
        "title": mock_video_title,
        "duration": 120
    })
    mock_subprocess_run.return_value = mock_result

    # --- 執行 ---
    result = downloader.download_media(url, output_dir, download_type=download_type)

    # --- 斷言 ---
    assert result["video_title"] == mock_video_title
    assert Path(result["output_path"]).name == expected_output_path.name
    mock_path_exists.assert_called_once()


def test_download_media_subprocess_error(mock_subprocess_run, tmp_path):
    """
    測試當 yt-dlp 執行失敗 (拋出 CalledProcessError) 時，download_media 是否能正確處理。
    """
    # --- 準備 ---
    url = "http://fake.youtube.com/watch?v=invalid"
    output_dir = tmp_path
    # 模擬 subprocess.run 拋出異常
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd="yt-dlp",
        stderr="This video is unavailable."
    )

    # --- 執行 & 斷言 ---
    with pytest.raises(downloader.DownloaderException) as excinfo:
        downloader.download_media(url, output_dir)

    assert "This video is unavailable." in str(excinfo.value)

def test_download_media_file_not_found_after_download(
    mock_subprocess_run,
    mocker, # 需要 mocker 來 patch Path.exists
    tmp_path
):
    """
    測試 yt-dlp 成功執行，但最終檔案在檔案系統中找不到的情境。
    """
    # --- 準備 ---
    url = "http://fake.youtube.com/watch?v=123"
    output_dir = tmp_path
    # 讓 Path.exists() 永遠回傳 False
    mocker.patch('pathlib.Path.exists', return_value=False)
    mocker.patch('pathlib.Path.glob', return_value=[]) # 確保 glob 也找不到檔案

    mock_result = MagicMock()
    mock_result.stdout = json.dumps({
        "_filename": str(tmp_path / "some_file.mp3"),
        "title": "Some Title"
    })
    mock_subprocess_run.return_value = mock_result

    # --- 執行 & 斷言 ---
    with pytest.raises(downloader.DownloaderException, match="下載後找不到對應的檔案"):
        downloader.download_media(url, output_dir)


def test_download_media_command_generation(mock_subprocess_run, mock_path_exists, tmp_path):
    """
    測試 download_media 是否能根據參數產生正確的 yt-dlp 指令。
    """
    # --- 準備 ---
    url = "http://fake.youtube.com/watch?v=custom"
    output_dir = tmp_path
    custom_filename = "我的自訂影片"
    cookies_file = tmp_path / "cookies.txt"
    cookies_file.touch()

    # JULES'S FIX: 為了防止後續的 json.loads 失敗，必須提供一個模擬的回傳值。
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({
        "_filename": str(tmp_path / "ignored.mp4"),
        "title": "ignored title",
        "duration": 0
    })
    mock_subprocess_run.return_value = mock_result

    # --- 執行 ---
    downloader.download_media(
        url,
        output_dir,
        download_type="video",
        custom_filename=custom_filename,
        cookies_file=str(cookies_file)
    )

    # --- 斷言 ---
    # 獲取傳遞給 subprocess.run 的參數
    called_args, _ = mock_subprocess_run.call_args
    command_list = called_args[0]

    # 檢查指令是否包含所有預期的部分
    assert "yt-dlp" in command_list
    assert "--merge-output-format" in command_list
    assert "mp4" in command_list
    assert "--cookies" in command_list
    assert str(cookies_file) in command_list
    # 檢查輸出模板是否使用了自訂檔名
    output_template_arg_index = command_list.index("-o") + 1
    assert custom_filename in command_list[output_template_arg_index]
