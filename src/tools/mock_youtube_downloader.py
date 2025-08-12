import json
import time
import argparse
import sys
from pathlib import Path

def main():
    """
    一個模擬的 YouTube 下載器。
    它會模仿真實工具的行為，印出進度 JSON 並在最後產出一個假的音訊檔案。
    """
    parser = argparse.ArgumentParser(description="模擬 YouTube 音訊下載。")
    parser.add_argument("--url", required=True, help="要處理的 YouTube URL。")
    parser.add_argument("--output-dir", required=True, help="儲存輸出檔案的目錄。")
    args = parser.parse_args()

    try:
        # 模擬下載進度 (JULES'S FIX: Print progress to stderr)
        print(json.dumps({"type": "progress", "percent": 10, "description": "正在連接模擬伺服器..."}), file=sys.stderr, flush=True)
        time.sleep(0.3)
        print(json.dumps({"type": "progress", "percent": 50, "description": "正在下載模擬音訊流..."}), file=sys.stderr, flush=True)
        time.sleep(0.5)
        print(json.dumps({"type": "progress", "percent": 100, "description": "正在完成模擬音訊檔案..."}), file=sys.stderr, flush=True)
        time.sleep(0.3)

        # 建立一個假的輸出檔案
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)

        # 從 URL 生成一個簡單的檔案名稱
        filename_stem = "".join(c for c in Path(args.url).name if c.isalnum())[:20]
        if not filename_stem:
            filename_stem = "default_mock_video"
        dummy_audio_path = output_dir / f"{filename_stem}_mock_audio.mp3"
        dummy_audio_path.write_text("這是一個模擬的音訊檔案。")

        # 產出最終的成功結果 JSON
        result = {
            "type": "result",
            "status": "completed",
            "output_path": str(dummy_audio_path),
            "video_title": f"'{args.url}' 的模擬影片標題",
            "duration_sec": 123,
            "mime_type": "audio/mp3"
        }
        print(json.dumps(result), flush=True)
        sys.exit(0)

    except Exception as e:
        # 產出錯誤結果 JSON
        error_result = {
            "type": "result",
            "status": "failed",
            "error": f"模擬下載器發生錯誤: {e}"
        }
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
