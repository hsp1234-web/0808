# src/tools/mp3_downloader.py
import argparse
import json
import logging
import sys
import subprocess
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger('mp3_downloader_tool')

def download_mp3(
    youtube_url: str,
    output_dir: Path,
    video_id: str
):
    """
    使用 yt-dlp 從 YouTube URL 下載 MP3 音訊。

    :param youtube_url: 要下載的 YouTube URL。
    :param output_dir: 儲存檔案的目錄。
    :param video_id: 用於命名檔案的唯一 ID。
    """
    log.info(f"開始下載 MP3，URL: {youtube_url}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 使用 video_id 作為檔案名稱，確保唯一性
    output_template = f"{str(output_dir / video_id)}.%(ext)s"

    command = [
        "yt-dlp",
        "--print-json",
        "-f", "bestaudio",
        "-x",  # --extract-audio
        "--audio-format", "mp3",
        "-o", output_template,
        youtube_url
    ]

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
        # 即使我們指定了檔名，還是從 yt-dlp 的輸出確認最終路徑
        final_filepath_str = video_info.get('_filename')

        if not final_filepath_str:
            log.error("無法從 yt-dlp 的輸出中確定檔案名稱。")
            raise RuntimeError("yt-dlp did not provide the output filename in its JSON.")

        # yt-dlp 可能會回傳轉檔前的副檔名，我們強制使用 .mp3
        final_path = Path(final_filepath_str).with_suffix(".mp3")

        # 如果檔案不存在，可能是因為 yt-dlp 的 _filename 有誤，我們自己組合
        if not final_path.exists():
            expected_path = output_dir / f"{video_id}.mp3"
            if expected_path.exists():
                final_path = expected_path
            else:
                 raise FileNotFoundError(f"在 {output_dir} 中找不到下載的 MP3 檔案。")


        final_result = {
            "status": "completed",
            "output_path": str(final_path),
            "video_title": video_info.get("title", "Unknown Title"),
            "duration": video_info.get("duration", 0)
        }

        log.info(f"✅ MP3 下載成功: {final_path}")
        return final_result

    except subprocess.CalledProcessError as e:
        log.error(f"❌ yt-dlp 執行失敗。返回碼: {e.returncode}")
        log.error(f"Stderr: {e.stderr}")
        raise RuntimeError(f"yt-dlp 執行失敗: {e.stderr}")
    except Exception as e:
        log.error(f"❌ 下載過程中發生未預期的錯誤: {e}", exc_info=True)
        raise e

def main():
    parser = argparse.ArgumentParser(description="YouTube MP3 下載工具 (使用 yt-dlp)。")
    parser.add_argument("--url", type=str, required=True, help="YouTube URL。")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存 MP3 的目錄。")
    parser.add_argument("--video-id", type=str, required=True, help="用於命名檔案的影片 ID。")

    args = parser.parse_args()

    try:
        result = download_mp3(
            args.url,
            Path(args.output_dir),
            args.video_id
        )
        # 將結果以 JSON 格式輸出到 stdout
        print(json.dumps(result))
    except Exception as e:
        # 將錯誤訊息以 JSON 格式輸出到 stderr
        print(json.dumps({"status": "failed", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
