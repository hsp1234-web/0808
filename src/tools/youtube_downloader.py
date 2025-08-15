# tools/youtube_downloader.py
import argparse
import json
import logging
import sys
import subprocess
from pathlib import Path

# --- 日誌設定 ---
# Log to stderr so that stdout can be used for JSON output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger('youtube_downloader_tool')

def download_media(
    youtube_url: str,
    output_dir: Path,
    download_type: str = "audio",
    custom_filename: str | None = None,
    cookies_file: str | None = None
):
    """
    使用 yt-dlp 從 YouTube URL 下載媒體（音訊或影片）。

    :param youtube_url: 要下載的 YouTube URL。
    :param output_dir: 儲存檔案的目錄。
    :param download_type: 'audio' 或 'video'。
    :param custom_filename: 自訂的檔案名稱 (不含副檔名)。
    :param cookies_file: 用於驗證的 cookies.txt 檔案路徑。
    """
    log.info(f"開始下載媒體，類型: {download_type}，URL: {youtube_url}")

    output_template = f"{str(output_dir / custom_filename)}.%(ext)s" if custom_filename else f"{str(output_dir / '%(title)s')}.%(ext)s"
    final_suffix = ".mp3" if download_type == "audio" else ".mp4"

    command = ["yt-dlp", "--print-json"]

    if download_type == "audio":
        command.extend([
            "-f", "bestaudio",
            "-x",  # --extract-audio
            "--audio-format", "mp3",
        ])
    else: # video
        command.extend([
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
        ])

    # 如果提供了 cookies 檔案路徑，則加入指令
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
            log.error("無法從 yt-dlp 的輸出中確定檔案名稱。")
            raise RuntimeError("yt-dlp did not provide the output filename in its JSON.")

        # yt-dlp 可能會回傳轉檔前的副檔名，我們強制使用我們期望的副檔名
        final_path = Path(final_filepath_str).with_suffix(final_suffix)

        # 在某些情況下，合併後的檔案名稱可能與 yt-dlp 報告的 _filename 不同，
        # 例如，當它從 .mkv 轉換為 .mp4 時。我們需要找到實際的檔案。
        if not final_path.exists():
            # 建立一個預期的路徑（基於標題或自訂名稱）
            expected_base = custom_filename or video_info.get("title", "unknown")
            # yt-dlp 會清理檔名，我們這裡做一個簡化版的模擬
            sanitized_base = "".join(c for c in expected_base if c.isalnum() or c in (' ', '_', '-')).rstrip()
            expected_path = output_dir / f"{sanitized_base}{final_suffix}"

            if expected_path.exists():
                final_path = expected_path
            else:
                log.warning(f"找不到預期的檔案 {final_path} 或 {expected_path}。將搜尋目錄...")
                # 在輸出目錄中搜尋最新的、符合副檔名的檔案作為最後手段
                files_in_dir = list(output_dir.glob(f"*{final_suffix}"))
                if files_in_dir:
                    latest_file = max(files_in_dir, key=lambda p: p.stat().st_mtime)
                    final_path = latest_file
                    log.info(f"找到最新的檔案作為下載結果: {final_path}")
                else:
                    raise FileNotFoundError(f"在 {output_dir} 中找不到任何 {final_suffix} 檔案。")


        final_result = {
            "type": "result",
            "status": "completed",
            "output_path": str(final_path),
            "video_title": video_info.get("title", "Unknown Title"),
            "duration_seconds": video_info.get("duration", 0)
        }

        print(json.dumps(final_result), flush=True)
        log.info(f"✅ 媒體下載成功: {final_path}")

    except subprocess.CalledProcessError as e:
        log.error(f"❌ yt-dlp 執行失敗。返回碼: {e.returncode}")
        stderr_text = e.stderr.lower()
        log.error(f"Stderr: {e.stderr}")

        # --- 根據計畫書，進行精細化錯誤判斷 ---
        error_code = "DOWNLOAD_FAILED"
        friendly_message = "下載失敗： 請確認您輸入的網址是否正確，且為一個有效的影音頁面。"

        if "this video is private" in stderr_text or "login required" in stderr_text or "authentication required" in stderr_text or "401" in stderr_text or "403" in stderr_text:
            error_code = "AUTH_REQUIRED"
            friendly_message = "下載失敗： 此內容可能為私人影片或需要會員資格才能存取。基於安全考量，本服務目前無法處理需要登入的內容。"

        elif "this video is not available in your country" in stderr_text:
            error_code = "GEO_RESTRICTED"
            friendly_message = "下載失敗： 抱歉，此內容因目標網站的地區限制而無法存取。"

        elif "too many requests" in stderr_text or "429" in stderr_text:
            error_code = "RATE_LIMITED"
            friendly_message = "下載失敗： 目標網站暫時限制了我們的存取請求，請稍後幾分鐘再試一次。"

        elif "no supported format found" in stderr_text or "unable to extract" in stderr_text or "invalid url" in stderr_text:
            error_code = "INVALID_URL"
            friendly_message = "下載失敗： 請確認您輸入的網址是否正確，或該頁面不包含可下載的影音內容。"

        # 建立結構化的錯誤回報
        error_result = {
            "type": "result",
            "status": "failed",
            "error": friendly_message, # 給前端顯示的友善訊息
            "error_code": error_code,      # 給前端進行邏輯判斷的代碼
            "technical_error": e.stderr  # 供內部除錯的原始錯誤訊息
        }
        print(json.dumps(error_result, ensure_ascii=False), flush=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"❌ 下載過程中發生未預期的錯誤: {e}", exc_info=True)
        error_result = {"type": "result", "status": "failed", "error": str(e)}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="YouTube 媒體下載工具 (使用 yt-dlp)。")
    parser.add_argument("--url", type=str, required=True, help="YouTube URL。")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存媒體的目錄。")
    parser.add_argument("--download-type", type=str, default="audio", choices=['audio', 'video'], help="下載類型：'audio' 或 'video'。")
    parser.add_argument("--custom-filename", type=str, default=None, help="自訂的檔案名稱 (不含副檔名)。")
    parser.add_argument("--cookies-file", type=str, default=None, help="用於驗證的 cookies.txt 檔案路徑。")

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    download_media(
        args.url,
        output_path,
        args.download_type,
        args.custom_filename,
        args.cookies_file
    )

if __name__ == "__main__":
    main()
