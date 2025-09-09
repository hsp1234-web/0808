# src/tests/test_gemini_uploader.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# HACK: 為了確保測試在任何環境下都能穩定執行，手動將 'src' 目錄加入系統路徑
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import gemini_uploader
from google.api_core import exceptions as google_exceptions

@pytest.fixture
def mock_genai(mocker):
    """模擬 google.generativeai 模組。"""
    return mocker.patch('tools.gemini_uploader.genai')

@pytest.fixture
def mock_os_getenv(mocker):
    """模擬 os.getenv 函式。"""
    return mocker.patch('os.getenv', return_value="fake_api_key")

def test_upload_file_success(mock_genai, mock_os_getenv, tmp_path):
    """
    測試 upload_file 函式在成功情境下的行為。
    """
    # --- 準備 ---
    # 建立一個假的檔案
    test_file = tmp_path / "test_audio.mp3"
    test_file.touch()

    # 模擬 genai.upload_file 的成功回傳值
    mock_file_resource = MagicMock()
    mock_file_resource.uri = "v1/files/mock-uri-123"
    mock_genai.upload_file.return_value = mock_file_resource

    # --- 執行 ---
    result = gemini_uploader.upload_file(test_file)

    # --- 斷言 ---
    # 斷言 API 金鑰被讀取
    mock_os_getenv.assert_called_once_with("GOOGLE_API_KEY")
    # 斷言 genai.configure 被呼叫
    mock_genai.configure.assert_called_once_with(api_key="fake_api_key")
    # 斷言 upload_file 被正確呼叫
    mock_genai.upload_file.assert_called_once_with(
        path=str(test_file),
        display_name=test_file.name,
        mime_type='audio/mp3'
    )
    # 斷言回傳值是預期的資源物件
    assert result == mock_file_resource
    assert result.uri == "v1/files/mock-uri-123"

def test_upload_file_api_error(mock_genai, mock_os_getenv, tmp_path):
    """
    測試當 Gemini API 呼叫失敗時，upload_file 是否能正確拋出異常。
    """
    # --- 準備 ---
    test_file = tmp_path / "test_audio.wav"
    test_file.touch()

    # 模擬 genai.upload_file 拋出 Google API 錯誤
    mock_genai.upload_file.side_effect = google_exceptions.GoogleAPICallError("API call failed")

    # --- 執行 & 斷言 ---
    with pytest.raises(gemini_uploader.UploaderException, match="Gemini API 呼叫失敗"):
        gemini_uploader.upload_file(test_file)

def test_upload_file_no_api_key(mocker, tmp_path):
    """
    測試當環境變數中沒有 API 金鑰時，upload_file 是否能正確拋出異常。
    """
    # --- 準備 ---
    # 讓 os.getenv 回傳 None
    mocker.patch('os.getenv', return_value=None)
    test_file = tmp_path / "test.txt"
    test_file.touch()

    # --- 執行 & 斷言 ---
    with pytest.raises(gemini_uploader.UploaderException, match="環境變數 'GOOGLE_API_KEY' 未設定。"):
        gemini_uploader.upload_file(test_file)

def test_upload_file_not_found(mock_os_getenv):
    """
    測試當要上傳的檔案不存在時，upload_file 是否能正確拋出異常。
    """
    # --- 準備 ---
    non_existent_file = Path("/tmp/this/file/does/not/exist.mp3")

    # --- 執行 & 斷言 ---
    with pytest.raises(gemini_uploader.UploaderException, match="找不到要上傳的檔案"):
        gemini_uploader.upload_file(non_existent_file)
