import json
import time
import argparse
import sys
from pathlib import Path
from weasyprint import HTML

def main():
    """
    一個模擬的 Gemini 處理器。
    它接收一個假的音訊檔案，模擬 AI 處理過程，並產出一個假的 PDF 報告。
    """
    parser = argparse.ArgumentParser(description="模擬 Gemini AI 處理與報告生成 (PDF)。")
    parser.add_argument("--audio-file", required=True, help="輸入的音訊檔案路徑。")
    parser.add_argument("--model", required=True, help="要使用的 Gemini 模型。")
    parser.add_argument("--video-title", required=True, help="原始影片標題。")
    parser.add_argument("--output-dir", required=True, help="儲存報告的目錄。")
    args = parser.parse_args()

    try:
        time.sleep(1) # 模擬處理時間

        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        filename_stem = Path(args.audio_file).stem

        # 1. 定義 HTML 內容
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>AI 分析報告 - {args.video_title}</title>
    <style>
        @font-face {{
            font-family: 'Noto Sans TC';
            src: url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap');
        }}
        body {{ font-family: 'Noto Sans TC', sans-serif; line-height: 1.6; padding: 2em; background-color: #f9f9f9; }}
        h1, h2 {{ color: #333; }}
        .card {{ background-color: white; border: 1px solid #ddd; padding: 1em; border-radius: 8px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>AI 分析報告</h1>
        <h2>影片標題：{args.video_title}</h2>
        <p>這是一份由 <strong>mock_gemini_processor.py</strong> 產生的模擬 PDF 報告。</p>
        <ul>
            <li>使用的模擬模型: <strong>{args.model}</strong></li>
            <li>處理的模擬音訊檔: <strong>{args.audio_file}</strong></li>
        </ul>
        <p>此報告確認了 PDF 產生流程可以被正確觸發。</p>
    </div>
</body>
</html>
"""

        # 2. 將 HTML 轉換為 PDF
        pdf_report_path = output_dir / f"{filename_stem}_AI_report.pdf"
        HTML(string=html_content, base_url=str(output_dir)).write_pdf(pdf_report_path)

        # 3. 產出最終的成功結果 JSON
        result = {
            "type": "result",
            "status": "completed",
            "pdf_report_path": str(pdf_report_path) # 回傳 PDF 路徑
        }
        print(json.dumps(result), flush=True)
        sys.exit(0)

    except Exception as e:
        # 產出錯誤結果 JSON
        error_result = {
            "type": "result",
            "status": "failed",
            "error": f"模擬 Gemini PDF 處理器發生錯誤: {e}"
        }
        print(json.dumps(error_result), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
