import pytest
import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src to path to allow direct import
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import gemini_processor

@pytest.fixture
def mock_successful_gemini_response():
    """Creates a mock of a successful Gemini response object."""
    response = MagicMock()
    response.text = "Mocked AI Response"
    response.usage_metadata.total_token_count = 100
    # This is the key: for a successful response, block_reason is None
    response.prompt_feedback.block_reason = None
    # And the finish_reason is STOP
    response.candidates = [MagicMock()]
    response.candidates[0].finish_reason.name = "STOP"
    return response

@pytest.fixture
def mock_file_system(mocker):
    """Mocks file system operations and prompt loading."""
    mocker.patch('pathlib.Path.exists', return_value=True)
    mocker.patch('builtins.open', mocker.mock_open())
    mocker.patch('tools.gemini_processor.load_prompts', return_value={
        "get_summary_and_transcript": "prompt1",
        "format_as_html": "prompt2"
    })
    return mocker

def test_process_audio_file_handles_title_correctly(mock_file_system, mock_successful_gemini_response, tmp_path, mocker):
    """
    Unit Test Case 1: Success Case
    Tests if the video_title is correctly passed through the processing chain.
    """
    # Arrange
    mocker.patch.dict(os.environ, {"GOOGLE_API_KEY": "a_valid_test_key"})

    # Mock the internal functions that make network calls
    mocker.patch('tools.gemini_processor.upload_to_gemini', return_value=MagicMock(uri="mock_uri"))
    # Now, the get_text and get_html functions will return our realistic successful response
    mocker.patch('tools.gemini_processor.get_summary_and_transcript', return_value=("summary", "transcript", mock_successful_gemini_response))
    mock_get_html = mocker.patch('tools.gemini_processor.generate_html_report', return_value=("<html></html>", mock_successful_gemini_response))

    test_audio_path = tmp_path / "test.mp3"
    output_dir = tmp_path / "reports"
    expected_title = "這是一個非常明確的測試標題"

    # Act
    gemini_processor.process_audio_file(
        audio_path=test_audio_path,
        model_name="gemini-pro-mock",
        video_title=expected_title,
        output_dir=output_dir,
        tasks="summary,transcript",
        output_format="html"
    )

    # Assert
    # Assert that our HTML generation function was called with the correct title
    mock_get_html.assert_called_once()
    args, kwargs = mock_get_html.call_args
    # `video_title` is the 4th positional argument (index 3)
    passed_title = args[3]
    assert passed_title == expected_title

def test_process_audio_file_handles_timeout(mock_file_system, tmp_path, mocker):
    """
    Unit Test Case 2: Timeout/Error Case
    Tests if the function correctly handles an exception from a sub-function.
    """
    # Arrange
    mocker.patch.dict(os.environ, {"GOOGLE_API_KEY": "a_valid_test_key"})

    # Mock the function that would time out
    mocker.patch('tools.gemini_processor.upload_to_gemini', side_effect=Exception("Simulated API Timeout"))

    test_audio_path = tmp_path / "test.mp3"
    output_dir = tmp_path / "reports"

    # Act & Assert
    with pytest.raises(Exception, match="Simulated API Timeout"):
        gemini_processor.process_audio_file(
            audio_path=test_audio_path,
            model_name="gemini-pro-mock",
            video_title="A title",
            output_dir=output_dir,
            tasks="summary,transcript",
            output_format="html"
        )
