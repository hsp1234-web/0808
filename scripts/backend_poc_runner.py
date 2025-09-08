# -*- coding: utf-8 -*-
import argparse
import os
import sys
import uuid
from datetime import datetime

# 為了能從 scripts 目錄執行，需要將專案根目錄加入到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.poc_tasks import db_poc
from src.poc_tasks import youtube_poc
from src.poc_tasks import transcriber_poc
from src.poc_tasks import gemini_poc
from src.poc_tasks.logging_poc import get_poc_logger, TIMEZONE

logger = get_poc_logger("backend_poc_runner")

def main():
    """
    POC 執行的主函式。
    """
    parser = argparse.ArgumentParser(description="後端 POC 執行器，用於處理單一 YouTube URL。")
    parser.add_argument("url", type=str, help="要處理的 YouTube URL。")
    parser.add_argument("--api-key", type=str, dest="api_key",
                        help="Google API 金鑰。如果未提供，將嘗試從 GOOGLE_API_KEY 環境變數讀取。")

    args = parser.parse_args()

    # 獲取 API 金鑰
    api_key = args.api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("錯誤: Google API 金鑰未提供。請使用 --api-key 參數或設定 GOOGLE_API_KEY 環境變數。")
        sys.exit(1)

    # --- 流程開始 ---
    task_id = f"poc-run-{uuid.uuid4()}"
    logger.info(f"========== [{task_id}] 新任務開始 ==========")
    logger.info(f"接收到 URL: {args.url}")

    # 1. 在資料庫中建立任務
    try:
        now = datetime.now(TIMEZONE).isoformat()
        db_poc.create_task(task_id, args.url, now)
        logger.info(f"[{task_id}] 已在資料庫中建立任務記錄。")
    except Exception as e:
        logger.error(f"[{task_id}] 無法在資料庫中建立任務: {e}", exc_info=True)
        sys.exit(1)

    # 2. 下載 YouTube 影片
    audio_file_path = youtube_poc.process_youtube_video(task_id, args.url)
    if not audio_file_path:
        logger.error(f"[{task_id}] 任務失敗於：影片下載階段。")
        logger.info(f"========== [{task_id}] 任務結束 ==========")
        sys.exit(1)

    logger.info(f"[{task_id}] 影片下載完成，音訊檔案位於: {audio_file_path}")

    # 3. 轉錄音訊檔案
    transcript = transcriber_poc.transcribe_audio(task_id, audio_file_path)
    # 下載的檔案是 POC 的中間產物，轉錄完成後即可清理
    if os.path.exists(audio_file_path):
        os.remove(audio_file_path)
        logger.info(f"[{task_id}] 已清理臨時音訊檔案: {audio_file_path}")

    if not transcript:
        logger.error(f"[{task_id}] 任務失敗於：音訊轉錄階段。")
        logger.info(f"========== [{task_id}] 任務結束 ==========")
        sys.exit(1)

    logger.info(f"[{task_id}] 音訊轉錄完成。")
    # logger.debug(f"[{task_id}] 轉錄內容: {transcript[:200]}...") # 避免日誌過於冗長

    # 4. 使用 Gemini 進行分析
    report_path = gemini_poc.analyze_text(task_id, transcript, api_key)
    if not report_path:
        logger.error(f"[{task_id}] 任務失敗於：Gemini 分析階段。")
        logger.info(f"========== [{task_id}] 任務結束 ==========")
        sys.exit(1)

    logger.info(f"[{task_id}] Gemini 分析完成，報告位於: {report_path}")
    logger.info(f"========== [{task_id}] 任務成功結束 ==========")


if __name__ == "__main__":
    main()
