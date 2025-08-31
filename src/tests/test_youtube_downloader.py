# src/tests/test_youtube_downloader.py
import pytest
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# 將 src 目錄加入 sys.path 以便 pytest 能找到模組
import sys
# JULES: 為了讓測試環境能正確引用 src 下的模組，需要將根目錄加入 sys.path
# 我們假設測試是從專案根目錄執行的
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools import youtube_downloader

# 測試用的常數
TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TEST_OUTPUT_DIR = Path("/tmp/test_downloads")
TEST_FILENAME = "my_awesome_video"
TEST_COOKIES_FILE = "/tmp/cookies.txt"

@pytest.fixture(autouse=True)
def setup_teardown(tmp_path):
    """在每次測試前後自動建立並清理測試目錄"""
    global TEST_OUTPUT_DIR
    TEST_OUTPUT_DIR = tmp_path
    # 不需要手動建立，因為 youtube_downloader.py 的 main() 會處理
    yield
    # 清理會在 tmp_path fixture 的幫助下自動完成

class TestYoutubeDownloader:
    """
    對 `youtube_downloader.py` 的 `download_media` 函式進行單元測試。
    """

    @patch('subprocess.run')
    def test_download_audio_success(self, mock_subprocess_run):
        """
        測試音訊下載成功的基本流程。
        """
        # 預計會被下載的檔案路徑
        expected_filepath = TEST_OUTPUT_DIR / f"{TEST_FILENAME}.mp3"

        # 模擬 yt-dlp 的 JSON 輸出
        mock_yt_dlp_output = {
            "_filename": str(expected_filepath),
            "title": "Mock Video Title",
            "duration": 120
        }
        mock_process_result = MagicMock()
        mock_process_result.stdout = json.dumps(mock_yt_dlp_output)
        mock_process_result.stderr = ""
        mock_process_result.returncode = 0
        mock_subprocess_run.return_value = mock_process_result

        # 模擬檔案存在
        with patch('pathlib.Path.exists', return_value=True):
            # 執行函式
            youtube_downloader.download_media(
                youtube_url=TEST_URL,
                output_dir=TEST_OUTPUT_DIR,
                download_type="audio",
                custom_filename=TEST_FILENAME
            )

        # 斷言 subprocess.run 被正確呼叫
        # 根據 youtube_downloader.py 的變更，更新預期的指令
        # 現在它應該透過 python -m yt_dlp 來執行
        expected_cmd = [
            sys.executable, "-m", "yt_dlp", "--print-json",
            "-f", "bestaudio", "-x", "--audio-format", "mp3",
            "-o", f"{TEST_OUTPUT_DIR / TEST_FILENAME}.%(ext)s",
            TEST_URL
        ]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )

    @patch('builtins.print')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('subprocess.run')
    def test_download_video_success(self, mock_subprocess_run, mock_path_exists, mock_print):
        """
        測試影片下載成功的基本流程。
        """
        expected_filepath = TEST_OUTPUT_DIR / f"{TEST_FILENAME}.mp4"
        mock_yt_dlp_output = {"_filename": str(expected_filepath), "title": "Test Video", "duration": 180}
        mock_subprocess_run.return_value = MagicMock(stdout=json.dumps(mock_yt_dlp_output), stderr="", returncode=0)

        youtube_downloader.download_media(
            youtube_url=TEST_URL,
            output_dir=TEST_OUTPUT_DIR,
            download_type="video",
            custom_filename=TEST_FILENAME
        )

        expected_cmd = [
            sys.executable, "-m", "yt_dlp", "--print-json",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "--merge-output-format", "mp4",
            "-o", f"{TEST_OUTPUT_DIR / TEST_FILENAME}.%(ext)s",
            TEST_URL
        ]
        mock_subprocess_run.assert_called_once_with(
            expected_cmd, capture_output=True, text=True, check=True, encoding='utf-8'
        )
        # 驗證最終輸出的 JSON
        final_json_output = json.loads(mock_print.call_args[0][0])
        assert final_json_output['status'] == '已完成'
        assert final_json_output['output_path'] == str(expected_filepath)

    @patch('builtins.print')
    @patch('subprocess.run')
    def test_download_fails_with_auth_error(self, mock_subprocess_run, mock_print):
        """
        測試下載因認證失敗的流程。
        """
        # 模擬 yt-dlp 拋出 CalledProcessError，並在 stderr 中包含認證相關訊息
        error_stderr = "ERROR: [youtube] This video is private. If you have access, provide authentication."
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="yt-dlp", stderr=error_stderr
        )

        with pytest.raises(SystemExit) as e:
             youtube_downloader.download_media(TEST_URL, TEST_OUTPUT_DIR)

        assert e.type == SystemExit
        assert e.value.code == 1

        # 驗證輸出的 JSON 包含正確的錯誤碼
        final_json_output = json.loads(mock_print.call_args[0][0])
        assert final_json_output['status'] == 'failed'
        assert final_json_output['error_code'] == 'AUTH_REQUIRED'
        assert "請提供 cookies.txt" in final_json_output['error']

    @patch('builtins.print')
    @patch('subprocess.run')
    def test_download_fails_with_generic_error(self, mock_subprocess_run, mock_print):
        """
        測試下載因通用錯誤失敗的流程。
        """
        error_stderr = "Some generic error from yt-dlp"
        mock_subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="yt-dlp", stderr=error_stderr
        )

        with pytest.raises(SystemExit):
            youtube_downloader.download_media(TEST_URL, TEST_OUTPUT_DIR)

        final_json_output = json.loads(mock_print.call_args[0][0])
        assert final_json_output['status'] == 'failed'
        assert final_json_output['error_code'] is None
        assert final_json_output['error'] == error_stderr

    @patch('builtins.print')
    @patch('pathlib.Path.exists')
    @patch('subprocess.run')
    def test_filename_fallback_logic(self, mock_subprocess_run, mock_path_exists, mock_print):
        """
        測試當 _filename 不存在但預期檔案存在時的備用邏輯。
        """
        # yt-dlp 回報一個路徑，但我們模擬它不存在
        reported_path = TEST_OUTPUT_DIR / "some_other_name.mp3"
        # 實際存在的檔案路徑
        expected_filepath = TEST_OUTPUT_DIR / f"{TEST_FILENAME}.mp3"

        mock_yt_dlp_output = {"_filename": str(reported_path), "title": TEST_FILENAME, "duration": 120}
        mock_subprocess_run.return_value = MagicMock(stdout=json.dumps(mock_yt_dlp_output))

        # 模擬 .exists() 的行為
        # 第一次呼叫 (on reported_path) 回傳 False
        # 第二次呼叫 (on expected_path) 回傳 True
        mock_path_exists.side_effect = [False, True]

        youtube_downloader.download_media(
            youtube_url=TEST_URL,
            output_dir=TEST_OUTPUT_DIR,
            download_type="audio",
            custom_filename=TEST_FILENAME
        )

        final_json_output = json.loads(mock_print.call_args[0][0])
        assert final_json_output['status'] == '已完成'
        # 斷言最終路徑是我們預期找到的那個，而不是 yt-dlp 回報的那個
        assert final_json_output['output_path'] == str(expected_filepath)

    @patch('pathlib.Path.is_file', return_value=True)
    @patch('pathlib.Path.exists', return_value=True)
    @patch('subprocess.run')
    def test_download_with_cookies(self, mock_subprocess_run, mock_path_exists, mock_is_file):
        """
        測試使用 cookies 檔案時，指令是否正確生成。
        """
        expected_filepath = TEST_OUTPUT_DIR / f"{TEST_FILENAME}.mp3"
        mock_yt_dlp_output = {"_filename": str(expected_filepath), "title": "Mock Video Title", "duration": 120}
        mock_subprocess_run.return_value = MagicMock(stdout=json.dumps(mock_yt_dlp_output))

        youtube_downloader.download_media(
            youtube_url=TEST_URL,
            output_dir=TEST_OUTPUT_DIR,
            custom_filename=TEST_FILENAME,
            cookies_file=TEST_COOKIES_FILE
        )

        # 斷言 "--cookies" 和檔案路徑在指令中
        called_cmd = mock_subprocess_run.call_args[0][0]
        assert "--cookies" in called_cmd
        assert TEST_COOKIES_FILE in called_cmd
