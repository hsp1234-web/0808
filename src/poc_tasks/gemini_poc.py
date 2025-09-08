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

    Args:
        task_id (str): 任務的唯一識別碼。
        text_content (str): 要分析的文字內容。
        api_key (str): Google API 金鑰。

    Returns:
        str | None: 若成功，返回報告檔案的路徑；若失敗，返回 None。
    """
    if not api_key:
        error_msg = "Google API 金鑰未提供，無法進行分析。"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

    started_at = datetime.now(TIMEZONE).isoformat()
    logger.info(f"[{task_id}] 開始使用 Gemini API 進行文字分析。")
    db_poc.update_task_status(task_id, "analyzing", started_at=started_at)

    try:
        # 設定 API 金鑰
        genai.configure(api_key=api_key)

        # 建立模型
        model = genai.GenerativeModel('gemini-pro')

        # 建立提示
        prompt = f"""請將以下逐字稿內容，整理成一份重點摘要，並用繁體中文輸出。

        ---
        {text_content}
        ---

        摘要：
        """

        logger.info(f"[{task_id}] 正在向 Gemini API 發送請求...")

        # 發送請求並設定超時
        response = model.generate_content(
            prompt,
            request_options={"timeout": API_TIMEOUT}
        )

        analysis_result = response.text
        logger.info(f"[{task_id}] 成功從 Gemini API 收到回應。")

        # 儲存報告
        report_filename = f"{task_id}.txt"
        report_filepath = os.path.join(REPORTS_DIR, report_filename)

        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(analysis_result)

        logger.info(f"[{task_id}] 分析報告已儲存至: {report_filepath}")

        # 更新資料庫
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


if __name__ == '__main__':
    # --- 執行測試 ---
    print("--- 開始執行 gemini_poc 模組測試 ---")

    # 從環境變數讀取 API 金鑰
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        print("\n!!! 測試跳過: 環境變數 'GOOGLE_API_KEY' 未設定。")
        print("請先設定您的 Google API 金鑰以執行此測試: export GOOGLE_API_KEY='YourApiKey'")
    else:
        # 1. 準備測試資料
        test_task_id = f"poc-test-{uuid.uuid4()}"
        now = datetime.now(TIMEZONE).isoformat()
        test_content = "這是一段測試文字，我們將會對它進行摘要。這個模組的目標是驗證與 Gemini API 的串接是否正常。"

        # 2. 在資料庫中建立一個測試任務
        db_poc.create_task(test_task_id, "text_analysis_test", now)
        print(f"在資料庫中建立了測試任務: {test_task_id}")

        # 3. 執行處理函式
        print("正在執行 analyze_text...")
        report_path = analyze_text(test_task_id, test_content, api_key)

        # 4. 驗證結果
        print("\n--- 驗證結果 ---")
        conn = db_poc.get_db_connection()
        task_data = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (test_task_id,)).fetchone()
        conn.close()

        if task_data:
            print(f"資料庫狀態: {task_data['status']}")

            if task_data['status'] == 'analysis_completed' and report_path:
                print(f"報告已成功儲存至: {report_path}")
                if os.path.exists(report_path):
                    print("驗證成功: 報告檔案存在。")
                    with open(report_path, 'r', encoding='utf-8') as f:
                        print("\n報告內容:")
                        print(f.read())
                    # 清理測試檔案
                    os.remove(report_path)
                    print(f"\n已清理測試報告: {report_path}")
                else:
                    print("!!! 驗證失敗: 報告檔案不存在。")
            else:
                print("!!! 測試失敗，任務未成功完成。")
                print(f"錯誤訊息: {task_data['error_message']}")
        else:
            print("!!! 驗證失敗: 在資料庫中找不到測試任務。")

    print("\n--- gemini_poc 模組測試結束 ---")
