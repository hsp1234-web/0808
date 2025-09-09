# src/tools/downloader.py
"""
一個獨立的媒體下載模組，封裝了對 yt-dlp 的呼叫。
"""
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# --- 日誌設定 ---
# 為了讓這個模組可以被其他部分引用，我們不在此處設定 basicConfig，
# 而是獲取一個 logger，由應用程式的進入點來統一設定日誌。
log = logging.getLogger(__name__)

class DownloaderException(Exception):
    """下載過程中發生的自訂錯誤。"""
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

def download_media(
    youtube_url: str,
    output_dir: Path,
    download_type: str = "audio",
    custom_filename: Optional[str] = None,
    cookies_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用 yt-dlp 從 YouTube URL 下載媒體（音訊或影片），並回傳結果字典。

    :param youtube_url: 要下載的 YouTube URL。
    :param output_dir: 儲存檔案的目錄。
    :param download_type: 'audio' 或 'video'。
    :param custom_filename: 自訂的檔案名稱 (不含副檔名)。
    :param cookies_file: 用於驗證的 cookies.txt 檔案路徑。
    :return: 一個包含下載結果資訊的字典。
    :raises DownloaderException: 如果下載失敗。
    """
    log.info(f"開始下載媒體，類型: {download_type}，URL: {youtube_url}")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_template = f"{str(output_dir / custom_filename)}.%(ext)s" if custom_filename else f"{str(output_dir / '%(title)s')}.%(ext)s"
    final_suffix = ".mp3" if download_type == "audio" else ".mp4"

    command = ["yt-dlp", "--print-json"]

    if download_type == "audio":
        command.extend(["-f", "bestaudio", "-x", "--audio-format", "mp3"])
    else: # video
        command.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "--merge-output-format", "mp4"])

    if cookies_file and Path(cookies_file).is_file():
        log.info(f"使用 Cookies 檔案: {cookies_file}")
        command.extend(["--cookies", cookies_file])

    command.extend(["-o", output_template, youtube_url])

    log.info(f"執行 yt-dlp 指令: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )

        video_info = json.loads(result.stdout)
        final_filepath_str = video_info.get('_filename')

        if not final_filepath_str:
            raise DownloaderException("yt-dlp 的輸出中未提供檔案名稱。")

        final_path = Path(final_filepath_str).with_suffix(final_suffix)

        if not final_path.exists():
            expected_base = custom_filename or video_info.get("title", "unknown")
            sanitized_base = "".join(c for c in expected_base if c.isalnum() or c in (' ', '_', '-')).rstrip()
            expected_path = output_dir / f"{sanitized_base}{final_suffix}"

            if expected_path.exists():
                final_path = expected_path
            else:
                files_in_dir = list(output_dir.glob(f"*{final_suffix}"))
                if files_in_dir:
                    latest_file = max(files_in_dir, key=lambda p: p.stat().st_mtime)
                    final_path = latest_file
                    log.info(f"找不到精確檔案，但找到最新的檔案作為下載結果: {final_path}")
                else:
                    raise FileNotFoundError(f"在 {output_dir} 中找不到任何 {final_suffix} 檔案。")

        final_result = {
            "output_path": str(final_path),
            "video_title": video_info.get("title", "Unknown Title"),
            "duration_seconds": video_info.get("duration", 0)
        }
        log.info(f"✅ 媒體下載成功: {final_path}")
        return final_result

    except subprocess.CalledProcessError as e:
        log.error(f"❌ yt-dlp 執行失敗。返回碼: {e.returncode}\nStderr: {e.stderr}")
        error_message = e.stderr
        error_code = None
        if "authentication" in error_message.lower() or "login required" in error_message.lower():
            error_code = "AUTH_REQUIRED"
            error_message = "此影片需要登入驗證。請提供 cookies.txt 檔案。"
        raise DownloaderException(error_message, error_code=error_code) from e

    except FileNotFoundError as e:
        log.error(f"❌ 下載後找不到對應的檔案: {e}")
        raise DownloaderException(f"下載後找不到對應的檔案: {e}") from e

    except Exception as e:
        log.error(f"❌ 下載過程中發生未預期的錯誤: {e}", exc_info=True)
        raise DownloaderException(f"下載過程中發生未預期的錯誤: {e}") from e
