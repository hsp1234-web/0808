# src/tests/test_report_storage.py
import pytest
from pathlib import Path

# HACK: 為了確保測試在任何環境下都能穩定執行，手動將 'src' 目錄加入系統路徑
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import report_storage

# pyfakefs 是一個 pytest fixture，我們只需要在測試函式的參數中宣告它即可
# 它會自動 patch 所有檔案系統相關的函式 (open, Path.exists, etc.)

def test_save_report_html(fs):
    """
    測試 save_report 函式儲存 HTML 格式的功能。
    'fs' fixture 由 pyfakefs 提供。
    """
    # --- 準備 ---
    output_dir = Path("/reports")
    # pyfakefs 會在記憶體中建立這個目錄
    fs.create_dir(output_dir)

    video_title = "My Test Video"
    content = {"html_content": "<h1>Test</h1><p>Hello</p>"}

    # --- 執行 ---
    result_path = report_storage.save_report(
        content=content,
        video_title=video_title,
        output_dir=output_dir,
        output_format="html"
    )

    # --- 斷言 ---
    # 斷言回傳的路徑是 Path 物件且存在
    assert isinstance(result_path, Path)
    assert result_path.exists()
    assert result_path.name.endswith(".html")
    assert "My_Test_Video" in result_path.name

    # 讀取虛擬檔案的內容並驗證
    with open(result_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    assert file_content == "<h1>Test</h1><p>Hello</p>"

def test_save_report_txt(fs):
    """
    測試 save_report 函式儲存 TXT 格式的功能。
    """
    # --- 準備 ---
    output_dir = Path("/reports")
    fs.create_dir(output_dir)

    video_title = "My Text Report"
    content = {
        "summary": "This is a summary.",
        "transcript": "This is the transcript."
    }
    expected_txt_content = "# My Text Report\n\n## 重點摘要\n\nThis is a summary.\n\n---\n\n## 詳細逐字稿\n\nThis is the transcript."


    # --- 執行 ---
    result_path = report_storage.save_report(
        content=content,
        video_title=video_title,
        output_dir=output_dir,
        output_format="txt"
    )

    # --- 斷言 ---
    assert result_path.exists()
    assert result_path.name.endswith(".txt")
    assert "My_Text_Report" in result_path.name

    file_content = result_path.read_text(encoding='utf-8')
    assert file_content == expected_txt_content

def test_save_report_unsupported_format(fs):
    """
    測試當提供不支援的格式時，函式是否會拋出 StorageException。
    """
    # --- 準備 ---
    output_dir = Path("/reports")
    fs.create_dir(output_dir)

    # --- 執行 & 斷言 ---
    with pytest.raises(report_storage.StorageException, match="不支援的輸出格式: pdf"):
        report_storage.save_report(
            content={},
            video_title="Bad Format",
            output_dir=output_dir,
            output_format="pdf"
        )
