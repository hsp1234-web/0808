# src/tests/test_url_extractor.py

import pytest
import sys
from pathlib import Path

# --- 路徑修正 ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from tools.url_extractor import extract_urls

# --- 測試案例 ---

@pytest.mark.parametrize("input_text, expected_urls", [
    # 測試基本案例
    ("查看這個連結 https://example.com 和這個 http://test.com", ["https://example.com", "http://test.com"]),
    # 測試文字開頭和結尾的網址
    ("https://start.com/page 這是開頭", ["https://start.com/page"]),
    ("這是結尾 http://end.com", ["http://end.com"]),
    # 測試沒有網址的文字
    ("這段文字沒有任何網址。", []),
    # 測試包含複雜字元和查詢參數的網址
    ("複雜網址 https://docs.google.com/document/d/14Z8zStyrPEZx9p0q9RfC-_tS3DJXs6EPidKk-Uc36eU/edit?usp=sharing 就在這裡", ["https://docs.google.com/document/d/14Z8zStyrPEZx9p0q9RfC-_tS3DJXs6EPidKk-Uc36eU/edit?usp=sharing"]),
    # 測試使用者提供的原始文字片段
    ("202505月[第467期] ▪︎https://drive.google.com/file/d/1T1GnR-7nb82GJqIzhfQsXAzvoScOP9OX/view?usp=drivesdk 狼友 https://docs.google.com/document/d/14Z8zStyrPEZx9p0q9RfC-_tS3DJXs6EPidKk-Uc36eU/edit?usp=sharing 20:45", ["https://drive.google.com/file/d/1T1GnR-7nb82GJqIzhfQsXAzvoScOP9OX/view?usp=drivesdk", "https://docs.google.com/document/d/14Z8zStyrPEZx9p0q9RfC-_tS3DJXs6EPidKk-Uc36eU/edit?usp=sharing"]),
    # 測試空字串
    ("", []),
])
def test_extract_urls(input_text, expected_urls):
    """
    測試 extract_urls 函式是否能正確從各種文字中提取網址。
    """
    assert extract_urls(input_text) == expected_urls
