# -*- coding: utf-8 -*-
import json
import time
import argparse
import sys
from pathlib import Path
import shutil
import uuid

def main():
    """
    一個真正的 YouTube 下載器模擬器。
    它不執行任何網路操作，只是建立一個假的媒體檔案並回傳一個成功的 JSON 結果。
    """
    parser = argparse.ArgumentParser(description="模擬 YouTube 音訊/影片下載。")
    parser.add_argument("--url", required=True, help="要處理的 YouTube URL。")
    parser.add_argument("--output-dir", required=True, help="儲存輸出檔案的目錄。")
    parser.add_argument("--download-type", default="audio", help="下載類型 (audio/video)。")
    # 忽略所有其他參數
    args, _ = parser.parse_known_args()

    try:
        time.sleep(0.5) # 模擬一個快速的處理延遲

        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)

        # 根據下載類型決定副檔名
        extension = ".mp4" if args.download_type == "video" else ".mp3"
        mime_type = "video/mp4" if args.download_type == "video" else "audio/mp3"

        # 定義測試治具的路徑
        script_dir = Path(__file__).resolve().parent
        fixture_path = script_dir.parent / "tests" / "fixtures" / "test_audio_v2.mp3"

        target_filename = f"e2e_test_{uuid.uuid4().hex[:8]}{extension}"
        target_path = output_dir / target_filename

        # 如果治具檔案不存在，就建立一個空檔案
        if not fixture_path.exists():
            target_path.touch()
        else:
            shutil.copy(fixture_path, target_path)

        # 產出最終的成功結果 JSON
        # JULES'S FIX (2025-09-02): 使用一個固定的、可預測的標題以簡化測試斷言
        result = {
            "type": "result",
            "status": "已完成",
            "output_path": str(target_path),
            "video_title": "Mocked YouTube Video Title",
            "duration_sec": 123,
            "mime_type": mime_type
        }
        print(json.dumps(result), flush=True)
        sys.exit(0)

    except Exception as e:
        error_result = {
            "type": "result",
            "status": "failed",
            "error": f"模擬下載器發生錯誤: {e}"
        }
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
