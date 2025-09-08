# -*- coding: utf-8 -*-
import os
import uuid
from datetime import datetime
import google.generativeai as genai

# 內部模組導入
from .logging_poc import get_poc_logger, TIMEZONE
from . import db_poc

# --- 常數定義 ---
REPORTS_DIR = "uploads_poc/reports"
API_TIMEOUT = 120  # API 呼叫超時時間（秒）

logger = get_poc_logger(__name__)

def analyze_text(task_id: str, text_content: str, api_key: str) -> str | None:
    """
    使用 Google Gemini API 分析文字內容並生成報告。
    """
    if not api_key:
        error_msg = "Google API 金鑰未提供，無法進行分析。"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

    if not text_content or not text_content.strip():
        error_msg = "輸入的文字內容為空，無法進行分析。"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

    started_at = datetime.now(TIMEZONE).isoformat()
    logger.info(f"[{task_id}] 開始使用 Gemini API 進行文字分析。")
    db_poc.update_task_status(task_id, "analyzing", started_at=started_at)

    try:
        genai.configure(api_key=api_key)

        # 透過 check_models.py 腳本程式化查詢後，我們使用一個確定可用的、高效的模型。
        # 包含 'models/' 前綴是必要的。
        model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

        prompt = f"""請將以下逐字稿內容，整理成一份重點摘要，並用繁體中文輸出。

        ---
        {text_content}
        ---

        摘要：
        """

        logger.info(f"[{task_id}] 正在向 Gemini API 發送請求...")
        response = model.generate_content(
            prompt,
            request_options={"timeout": API_TIMEOUT}
        )

        analysis_result = response.text
        logger.info(f"[{task_id}] 成功從 Gemini API 收到回應。")

        report_filename = f"{task_id}.txt"
        report_filepath = os.path.join(REPORTS_DIR, report_filename)

        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(analysis_result)

        logger.info(f"[{task_id}] 分析報告已儲存至: {report_filepath}")

        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.update_task_on_completion(
            task_id, "analysis_completed", finished_at, report_path=report_filepath
        )

        return report_filepath

    except Exception as e:
        error_msg = f"與 Gemini API 互動時發生錯誤: {e}"
        logger.error(f"[{task_id}] {error_msg}", exc_info=True)
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None
