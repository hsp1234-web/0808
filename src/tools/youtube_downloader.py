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
    download_type: str = 'audio',
    custom_filename: str | None = None,
    cookies_path: Path | None = None
):
    """
    Downloads media from a YouTube URL using yt-dlp, supporting both audio and video.
    """
    log.info(f"開始下載 {download_type}，URL: {youtube_url}")

    # Determine the output template
    output_template = f"{str(output_dir / custom_filename)}.%(ext)s" if custom_filename else f"{str(output_dir / '%(title)s')}.%(ext)s"

    # Base command
    command = ["yt-dlp", "--print-json", "-o", output_template]

    # Add cookies if available
    if cookies_path and cookies_path.exists():
        log.info(f"找到 Cookies 檔案，將其加入指令: {cookies_path}")
        command.extend(["--cookies", str(cookies_path)])
    else:
        log.info("未提供或找不到 Cookies 檔案。")

    # Add format specific options
    expected_extension = ""
    if download_type == 'video':
        command.extend([
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4"
        ])
        expected_extension = ".mp4"
    else: # Default to audio
        command.extend([
            "-f", "bestaudio",
            "-x", # --extract-audio
            "--audio-format", "mp3"
        ])
        expected_extension = ".mp3"

    # Add the URL at the end
    command.append(youtube_url)

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

        # Ensure the final path has the correct extension we expect
        final_path = Path(final_filepath_str).with_suffix(expected_extension)

        if not final_path.exists():
            # This can happen if the filename from yt-dlp differs slightly from what Path() expects.
            # A robust fallback is to trust yt-dlp's reported filename directly if the first attempt fails.
            final_path_alt = Path(final_filepath_str)
            if final_path_alt.exists():
                final_path = final_path_alt
            else:
                log.error(f"yt-dlp 執行成功，但找不到預期的輸出檔案: {final_path} 或 {final_path_alt}")
                raise FileNotFoundError(f"Downloaded file not found at {final_path}")


        final_result = {
            "type": "result",
            "status": "completed",
            "output_path": str(final_path),
            "video_title": video_info.get("title", "Unknown Title"),
            "duration_seconds": video_info.get("duration", 0),
            "download_type": download_type # Pass back the type for clarity
        }

        # The final JSON for api_server.py is printed to stdout
        print(json.dumps(final_result), flush=True)
        log.info(f"✅ {download_type} 下載成功: {final_path}")

    except subprocess.CalledProcessError as e:
        log.error(f"❌ yt-dlp 執行失敗。返回碼: {e.returncode}")
        # Friendly error for auth issues
        stderr_text = e.stderr
        if "Sign in to confirm you're not a bot" in stderr_text:
            log.error("偵測到 YouTube 驗證問題。")
            stderr_text = "YouTube 需要登入驗證。請在前端介面中上傳 cookies.txt 檔案後再試一次。"

        log.error(f"Stderr: {e.stderr}") # Log original stderr for debugging
        error_result = {"type": "result", "status": "failed", "error": stderr_text}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"❌ 下載過程中發生未預期的錯誤: {e}", exc_info=True)
        error_result = {"type": "result", "status": "failed", "error": str(e)}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="YouTube 媒體下載工具 (使用 yt-dlp)。")
    parser.add_argument("--url", type=str, required=True, help="YouTube URL.")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存檔案的目錄。")
    parser.add_argument("--download-type", type=str, default='audio', choices=['audio', 'video'], help="要下載的媒體類型 (audio 或 video)。")
    parser.add_argument("--custom-filename", type=str, default=None, help="自訂的檔案名稱 (不含副檔名)。")
    parser.add_argument("--cookies-path", type=str, default=None, help="cookies.txt 檔案的路徑。")

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cookies_file = Path(args.cookies_path) if args.cookies_path else None

    download_media(args.url, output_path, args.download_type, args.custom_filename, cookies_file)

if __name__ == "__main__":
    main()
