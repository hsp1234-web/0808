# tools/youtube_downloader.py
import argparse
import json
import logging
import sys
import time
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)] # 確保日誌輸出到 stdout
)
log = logging.getLogger('youtube_downloader_tool')

# --- 核心下載邏輯 ---
# 這些輔助函式改編自 colab.py
def sanitize_filename(title, max_len=60):
    """清理檔案名稱，移除無效字元。"""
    if not title:
        title = "untitled_audio"
    # 移除會導致路徑問題的字元
    title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    title = title.replace(" ", "_")
    return title[:max_len]

def format_bytes(size_bytes):
    """格式化位元組大小為可讀字串。"""
    if size_bytes == 0:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size_bytes >= power and n < len(power_labels) - 1:
        size_bytes /= power
        n += 1
    return f"{size_bytes:.2f} {power_labels[n]}"

# --- Pytube 進度回呼 ---
_start_time = 0
_total_size = 0
_bytes_downloaded = 0

def on_pytube_progress(stream, chunk, bytes_remaining):
    """Pytube 下載進度回呼函式，將進度以 JSON 格式印出。"""
    global _total_size, _bytes_downloaded, _start_time
    if _total_size == 0:
        _total_size = stream.filesize
        _bytes_downloaded = 0
        _start_time = time.time()

    _bytes_downloaded = _total_size - bytes_remaining
    percentage = (_bytes_downloaded / _total_size) * 100 if _total_size > 0 else 0

    elapsed_time = time.time() - _start_time
    speed = _bytes_downloaded / elapsed_time if elapsed_time > 0 else 0

    progress_data = {
        "type": "progress",
        "percent": round(percentage, 2),
        "downloaded_bytes": _bytes_downloaded,
        "total_bytes": _total_size,
        "speed_bytes_per_sec": round(speed),
        "description": f"Downloading... {format_bytes(_bytes_downloaded)} / {format_bytes(_total_size)}"
    }
    print(json.dumps(progress_data), flush=True)


def download_audio(youtube_url: str, output_dir: Path):
    """
    從 YouTube 下載音訊。
    """
    global _total_size, _bytes_downloaded, _start_time
    # 重設全域進度變數
    _total_size = 0
    _bytes_downloaded = 0
    _start_time = 0

    try:
        from pytubefix import YouTube
        from pytubefix.exceptions import RegexMatchError, VideoUnavailable

        log.info(f"🔗 Connecting to YouTube: {youtube_url}")
        yt = YouTube(youtube_url, on_progress_callback=on_pytube_progress)

        log.info(f"🎬 Video Title: {yt.title}")
        log.info(f"⏱️ Duration: {yt.length} seconds")

        # 篩選出純音訊流並下載
        audio_stream = yt.streams.get_audio_only()
        if not audio_stream:
            # 作為備用方案，尋找其他常見的音訊格式
            audio_stream = yt.streams.filter(only_audio=True, file_extension='m4a').order_by('abr').desc().first()
        if not audio_stream:
            raise RuntimeError("No suitable audio-only stream found for this video.")

        sanitized_title = sanitize_filename(yt.title)
        # 讓 pytube 決定副檔名，但我們指定檔名
        final_filename = f"{sanitized_title}.{audio_stream.subtype}"

        log.info(f"⏳ Starting download to {output_dir / final_filename}...")
        downloaded_path = audio_stream.download(output_path=str(output_dir), filename=final_filename)
        log.info(f"✅ Download complete!")

        # 下載完成後，輸出最終結果的 JSON
        final_result = {
            "type": "result",
            "status": "completed",
            "output_path": str(downloaded_path),
            "video_title": yt.title,
            "duration_seconds": yt.length
        }
        print(json.dumps(final_result), flush=True)

    except (RegexMatchError, VideoUnavailable) as e:
        log.error(f"❌ Video not available or URL is invalid: {e}")
        error_result = {"type": "result", "status": "failed", "error": str(e)}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)
    except Exception as e:
        log.critical(f"❌ An unexpected error occurred during download: {e}", exc_info=True)
        error_result = {"type": "result", "status": "failed", "error": str(e)}
        print(json.dumps(error_result), flush=True)
        sys.exit(1)


def main():
    """
    主函數，解析命令列參數並執行下載。
    """
    parser = argparse.ArgumentParser(description="YouTube 音訊下載工具。")
    parser.add_argument("--url", type=str, required=True, help="要下載的 YouTube 影片 URL。")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存下載音訊的目錄。")

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    download_audio(args.url, output_path)

if __name__ == "__main__":
    main()
