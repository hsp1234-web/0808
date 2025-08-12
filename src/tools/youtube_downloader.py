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

def download_audio(youtube_url: str, output_dir: Path, custom_filename: str | None = None):
    """
    Downloads audio from a YouTube URL using yt-dlp.
    """
    log.info(f"開始下載音訊，URL: {youtube_url}")

    # If a custom filename is given, use it. Otherwise, let yt-dlp use the video title.
    # The '.%(ext)s' part is crucial for yt-dlp to add the correct file extension.
    output_template = f"{str(output_dir / custom_filename)}.%(ext)s" if custom_filename else f"{str(output_dir / '%(title)s')}.%(ext)s"

    command = [
        "yt-dlp",
        "--print-json",
        "-f", "bestaudio",
        "-x", # --extract-audio
        "--audio-format", "mp3",
        "-o", output_template,
        youtube_url
    ]

    log.info(f"執行 yt-dlp 指令: {' '.join(command)}")

    try:
        # Using subprocess.run to capture output and wait for completion
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True, # Will raise CalledProcessError if yt-dlp returns a non-zero exit code
            encoding='utf-8'
        )

        # The JSON output from yt-dlp is in stdout
        video_info = json.loads(result.stdout)

        # When using -o, the `_filename` key in the JSON output gives the final calculated path.
        # This is the most reliable way to get the filename as sanitized by yt-dlp.
        final_filepath_str = video_info.get('_filename')

        if not final_filepath_str:
             log.error("無法從 yt-dlp 的輸出中確定檔案名稱。")
             raise RuntimeError("yt-dlp did not provide the output filename in its JSON.")

        # The path from yt-dlp might have the original extension before conversion.
        # We know we requested mp3, so we ensure the final path reflects that.
        final_path = Path(final_filepath_str).with_suffix('.mp3')

        if not final_path.exists():
            log.error(f"yt-dlp 執行成功，但找不到預期的輸出檔案: {final_path}")
            # This can happen if the filesystem has characters yt-dlp handles differently
            # than Python's path manipulation. It's a rare edge case.
            raise FileNotFoundError(f"Downloaded file not found at {final_path}")

        final_result = {
            "type": "result",
            "status": "completed",
            "output_path": str(final_path),
            "video_title": video_info.get("title", "Unknown Title"),
            "duration_seconds": video_info.get("duration", 0)
        }

        # The final JSON for api_server.py is printed to stdout
        print(json.dumps(final_result), flush=True)
        log.info(f"✅ 音訊下載成功: {final_path}")

    except subprocess.CalledProcessError as e:
        log.error(f"❌ yt-dlp 執行失敗。返回碼: {e.returncode}")
        log.error(f"Stderr: {e.stderr}")
        error_result = {"type": "result", "status": "failed", "error": e.stderr}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)
    except Exception as e:
        log.error(f"❌ 下載過程中發生未預期的錯誤: {e}", exc_info=True)
        error_result = {"type": "result", "status": "failed", "error": str(e)}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="YouTube 音訊下載工具 (使用 yt-dlp)。")
    parser.add_argument("--url", type=str, required=True, help="YouTube URL.")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存音訊的目錄。")
    parser.add_argument("--custom-filename", type=str, default=None, help="自訂的檔案名稱 (不含副檔名)。")

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    download_audio(args.url, output_path, args.custom_filename)

if __name__ == "__main__":
    main()
