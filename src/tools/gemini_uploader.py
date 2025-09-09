# src/tools/gemini_uploader.py
"""
一個獨立的模組，專門負責將檔案上傳到 Gemini API。
"""
import logging
import os
from pathlib import Path
from typing import Any, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

log = logging.getLogger(__name__)

class UploaderException(Exception):
    """檔案上傳過程中發生的自訂錯誤。"""
    pass

def upload_file(
    file_path: Path,
    display_name: Optional[str] = None
) -> Any:
    """
    將本地檔案上傳到 Gemini Files API。

    :param file_path: 要上傳的本地檔案的路徑。
    :param display_name: 在 Gemini API 中顯示的檔案名稱。如果為 None，則使用檔案的原始名稱。
    :return: Gemini API 回傳的檔案資源物件。
    :raises UploaderException: 如果上傳失敗或發生 API 錯誤。
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise UploaderException("環境變數 'GOOGLE_API_KEY' 未設定。")

    try:
        # JULES'S FIX: 在呼叫 API 前先檢查檔案是否存在，讓錯誤更明確
        if not file_path.exists():
            raise FileNotFoundError(f"要上傳的檔案不存在: {file_path}")

        genai.configure(api_key=api_key)

        log.info(f"☁️ 正在上傳檔案 '{file_path}' 至 Gemini Files API...")

        # 確定 MIME 類型
        ext = file_path.suffix.lower()
        mime_map = {
            '.mp3': 'audio/mp3', '.m4a': 'audio/m4a', '.aac': 'audio/aac',
            '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.flac': 'audio/flac',
            '.webm': 'audio/webm', '.mp4': 'audio/mp4'
        }
        # Gemini 目前偏好 aac 而非 m4a/mp4
        if ext in ['.m4a', '.mp4']:
            mime_type = 'audio/aac'
        else:
            mime_type = mime_map.get(ext, 'application/octet-stream')

        # 上傳檔案
        gemini_file = genai.upload_file(
            path=str(file_path),
            display_name=display_name or file_path.name,
            mime_type=mime_type
        )

        log.info(f"✅ 檔案上傳成功。Gemini File URI: {gemini_file.uri}")
        return gemini_file

    except google_exceptions.GoogleAPICallError as e:
        log.error(f"🔴 上傳時發生 Google API 錯誤: {e}")
        raise UploaderException(f"Gemini API 呼叫失敗: {e}") from e
    except FileNotFoundError:
        log.error(f"🔴 找不到要上傳的檔案: {file_path}")
        raise UploaderException(f"找不到要上傳的檔案: {file_path}")
    except Exception as e:
        log.error(f"🔴 上傳過程中發生未預期的錯誤: {e}", exc_info=True)
        raise UploaderException(f"上傳過程中發生未預期的錯誤: {e}") from e
