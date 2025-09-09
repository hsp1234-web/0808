# src/tools/report_storage.py
"""
一個獨立的模組，專門負責將分析結果儲存為報告檔案。
"""
import logging
import re
import time
from pathlib import Path
from typing import Dict, Any

log = logging.getLogger(__name__)

class StorageException(Exception):
    """檔案儲存過程中發生的自訂錯誤。"""
    pass

def _sanitize_filename(title: str, max_len: int = 60) -> str:
    """
    清理字串，使其成為一個有效的檔案名稱。
    """
    if not title:
        title = "untitled_document"
    # 移除無效字元
    title = re.sub(r'[\\/*?:"<>|]', "_", title)
    title = title.replace(" ", "_")
    # 將多個底線替換為單一底線
    title = re.sub(r"_+", "_", title)
    title = title.strip('_')
    # 截斷到最大長度
    return title[:max_len]

def save_report(
    content: Dict[str, Any],
    video_title: str,
    output_dir: Path,
    output_format: str = "html"
) -> Path:
    """
    將分析結果儲存為 HTML 或 TXT 報告檔案。

    :param content: 一個包含 'summary' 和 'transcript' 的字典。
    :param video_title: 用於生成檔名的影片標題。
    :param output_dir: 儲存報告的目錄。
    :param output_format: 'html' 或 'txt'。
    :return: 儲存的報告檔案的路徑。
    :raises StorageException: 如果儲存失敗。
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        sanitized_title = _sanitize_filename(video_title)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        final_filename_base = f"{sanitized_title}_{timestamp}_AI_Report"

        if output_format == 'html':
            report_content = content.get("html_content", "<html><body>報告內容為空。</body></html>")
            file_extension = ".html"
        elif output_format == 'txt':
            summary = content.get('summary', '無摘要。')
            transcript = content.get('transcript', '無逐字稿。')
            report_content = f"# {video_title}\n\n## 重點摘要\n\n{summary}\n\n---\n\n## 詳細逐字稿\n\n{transcript}"
            file_extension = ".txt"
        else:
            raise StorageException(f"不支援的輸出格式: {output_format}")

        output_path = output_dir / f"{final_filename_base}{file_extension}"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        log.info(f"✅ 報告已成功儲存至: {output_path}")
        return output_path

    except (IOError, OSError) as e:
        log.error(f"🔴 寫入報告檔案時發生 I/O 錯誤: {e}", exc_info=True)
        raise StorageException(f"寫入檔案失敗: {e}") from e
    except Exception as e:
        log.error(f"🔴 儲存報告時發生未預期的錯誤: {e}", exc_info=True)
        raise StorageException(f"儲存報告時發生未預期錯誤: {e}") from e
