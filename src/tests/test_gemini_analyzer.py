# src/tests/test_gemini_analyzer.py
import pytest
from unittest.mock import MagicMock, patch

# HACK: 為了確保測試在任何環境下都能穩定執行，手動將 'src' 目錄加入系統路徑
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import gemini_analyzer

# --- Fixtures ---

@pytest.fixture
def mock_model():
    """提供一個模擬的 Gemini GenerativeModel 物件。"""
    return MagicMock()

@pytest.fixture
def mock_file_resource():
    """提供一個模擬的 Gemini 檔案資源物件。"""
    return MagicMock()

@pytest.fixture(autouse=True)
def mock_load_prompts(mocker):
    """自動模擬 load_prompts 函式，回傳假的提示詞。"""
    prompts = {
        "get_summary_and_transcript": "為 '{video_title}' 產生摘要與逐字稿。",
        "format_as_html": "將摘要: {summary_text_for_html} 和逐字稿: {transcript_text_for_html} 轉為 HTML。"
    }
    return mocker.patch('tools.gemini_analyzer.load_prompts', return_value=prompts)

# --- Test Cases ---

def test_get_summary_and_transcript_success(mock_model, mock_file_resource):
    """
    測試 get_summary_and_transcript 函式在成功情境下的行為。
    """
    # --- 準備 ---
    # 模擬 _generate_content 的回傳值
    mock_response = MagicMock()
    mock_response.text = "[重點摘要開始]這是摘要。[重點摘要結束]\n[詳細逐字稿開始]這是逐字稿。[詳細逐字稿結束]"
    mock_response.usage_metadata.total_token_count = 123

    with patch('tools.gemini_analyzer._generate_content', return_value=mock_response) as mock_gen_content:
        # --- 執行 ---
        summary, transcript, tokens = gemini_analyzer.get_summary_and_transcript(
            model=mock_model,
            gemini_file_resource=mock_file_resource,
            video_title="測試影片",
            original_filename="test.mp3"
        )

        # --- 斷言 ---
        # 斷言 _generate_content 被正確呼叫
        mock_gen_content.assert_called_once()
        # 斷言結果被正確解析
        assert summary == "這是摘要。"
        assert transcript == "這是逐字稿。"
        assert tokens == 123

def test_generate_html_report_success(mock_model):
    """
    測試 generate_html_report 函式在成功情境下的行為。
    """
    # --- 準備 ---
    mock_response = MagicMock()
    # 模擬模型可能回傳的 markdown 格式
    mock_response.text = "```html\n<!doctype html><html><body>報告</body></html>\n```"
    mock_response.usage_metadata.total_token_count = 45

    with patch('tools.gemini_analyzer._generate_content', return_value=mock_response) as mock_gen_content:
        # --- 執行 ---
        html, tokens = gemini_analyzer.generate_html_report(
            model=mock_model,
            summary="摘要",
            transcript="逐字稿",
            video_title="HTML 報告"
        )

        # --- 斷言 ---
        mock_gen_content.assert_called_once()
        # 斷言 HTML 被正確清理
        assert html == "<!doctype html><html><body>報告</body></html>"
        assert tokens == 45

def test_analyzer_handles_safety_blocking(mock_model, mock_file_resource):
    """
    測試當 API 因安全設定而阻擋請求時，分析函式是否能正確拋出異常。
    """
    # --- 準備 ---
    # 模擬一個被阻擋的回應
    mock_response = MagicMock()
    mock_response.prompt_feedback.block_reason.name = "SAFETY"
    # 當被阻擋時，通常沒有 .text 屬性，或者為空
    type(mock_response).text = None

    # JULES'S FIX: 不再模擬 _generate_content，而是模擬更底層的 model.generate_content
    # 這樣才能測試 _generate_content 內部的錯誤處理邏輯。
    mock_model.generate_content.return_value = mock_response

    # --- 執行 & 斷言 ---
    with pytest.raises(gemini_analyzer.AnalyzerException, match="請求被 Gemini 安全設定阻擋"):
        gemini_analyzer.get_summary_and_transcript(
            model=mock_model,
            gemini_file_resource=mock_file_resource,
            video_title="危險影片",
            original_filename="danger.mp3"
        )

    # 驗證 model.generate_content 確實被呼叫了
    mock_model.generate_content.assert_called_once()
