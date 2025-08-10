import json
import time
import argparse
import sys
from pathlib import Path

def main():
    """
    一個模擬的 Gemini 處理器。
    它接收一個假的音訊檔案，模擬 AI 處理過程，並產出一個假的 HTML 報告。
    """
    parser = argparse.ArgumentParser(description="模擬 Gemini AI 處理與報告生成。")
    parser.add_argument("--audio-file", required=True, help="輸入的音訊檔案路徑。")
    parser.add_argument("--model", required=True, help="要使用的 Gemini 模型。")
    parser.add_argument("--video-title", required=True, help="原始影片標題。")
    parser.add_argument("--output-dir", required=True, help="儲存報告的目錄。")
    args = parser.parse_args()

    try:
        # 模擬處理進度
        print(json.dumps({"type": "progress", "detail": f"正在使用模擬模型 '{args.model}' 分析音訊..."}), flush=True)
        time.sleep(0.8)
        print(json.dumps({"type": "progress", "detail": "模擬 AI 正在生成摘要..."}), flush=True)
        time.sleep(0.4)
        print(json.dumps({"type": "progress", "detail": "正在將結果格式化為模擬 HTML 報告..."}), flush=True)
        time.sleep(0.8)

        # 建立一個假的 HTML 報告檔案
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)

        # 從音訊檔名生成報告檔名
        filename_stem = Path(args.audio_file).stem
        dummy_report_path = output_dir / f"{filename_stem}_AI生成報告.html"

        html_content = f"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>模擬 AI 報告 - {args.video_title}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; padding: 2em; background-color: #f9f9f9; }}
        h1, h2 {{ color: #333; }}
        .card {{ background-color: white; border: 1px solid #ddd; padding: 1em; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>模擬 AI 分析報告</h1>
        <h2>影片標題：{args.video_title}</h2>
        <p>這是一份由 <strong>mock_gemini_processor.py</strong> 產生的模擬報告。</p>
        <ul>
            <li>使用的模擬模型: <strong>{args.model}</strong></li>
            <li>處理的模擬音訊檔: <strong>{args.audio_file}</strong></li>
        </ul>
        <p>此報告確認了從前端到後端工具的完整流程可以被正確觸發。</p>
    </div>
</body>
</html>
"""
        dummy_report_path.write_text(html_content, encoding='utf-8')

        # 產出最終的成功結果 JSON
        result = {
            "type": "result",
            "status": "completed",
            "html_report_path": str(dummy_report_path)
        }
        print(json.dumps(result), flush=True)
        sys.exit(0)

    except Exception as e:
        # 產出錯誤結果 JSON
        error_result = {
            "type": "result",
            "status": "failed",
            "error": f"模擬 Gemini 處理器發生錯誤: {e}"
        }
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
