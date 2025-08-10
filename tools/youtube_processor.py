# tools/youtube_processor.py
import argparse
import sys
import time
import json
import logging
from pathlib import Path

# --- 日誌設定 ---
# 設定一個基本的日誌器，以便 api_server 可以捕捉其輸出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('youtube_processor')

def process_video(youtube_url: str, gemini_model: str, output_dir: str):
    """
    處理單一 YouTube 影片的核心函式。
    (目前為模擬版本)
    """
    log.info(f"▶️ 開始處理 YouTube 影片: {youtube_url}")
    log.info(f"🤖 使用 Gemini 模型: {gemini_model}")
    log.info(f"📂 輸出目錄: {output_dir}")

    try:
        # 步驟 1: (模擬) 下載音訊
        log.info("Downloading audio...")
        time.sleep(3) # 模擬耗時操作
        log.info("✅ 音訊下載完成。")

        # 步驟 2: (模擬) AI 分析
        log.info("Analyzing with Gemini...")
        time.sleep(5) # 模擬耗時操作
        log.info("✅ AI 分析完成。")

        # 步驟 3: (模擬) 產生報告
        Path(output_dir).mkdir(exist_ok=True)
        # 使用 UUID 來避免檔名衝突
        import uuid
        report_path = Path(output_dir) / f"report_{uuid.uuid4()}.html"
        report_content = f"""
        <html>
            <head>
                <meta charset="UTF-8">
                <title>分析報告: {youtube_url}</title>
            </head>
            <body>
                <h1>{youtube_url} 的分析報告</h1>
                <p>使用模型: {gemini_model}</p>
                <p>這是一個在 {time.ctime()} 自動生成的模擬報告。</p>
            </body>
        </html>
        """
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        log.info(f"✅ 報告已生成: {report_path}")

        # 以 JSON 格式輸出最終結果，供 api_server 解析
        final_result = {
            "status": "completed",
            "report_path": str(report_path)
        }
        print(json.dumps(final_result))

    except Exception as e:
        log.error(f"❌ 處理影片時發生錯誤: {e}", exc_info=True)
        error_result = {
            "status": "failed",
            "error": str(e)
        }
        # 將錯誤訊息也以 JSON 格式輸出到 stdout，讓 api_server 知道
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="鳳凰音訊轉錄儀 - YouTube 處理工具")
    parser.add_argument("--youtube_url", required=True, help="要處理的 YouTube 影片 URL。")
    parser.add_argument("--gemini_model", required=True, help="用於分析的 Gemini 模型。")
    parser.add_argument("--output_dir", default="reports", help="儲存報告的目錄。")

    args = parser.parse_args()

    process_video(args.youtube_url, args.gemini_model, args.output_dir)
