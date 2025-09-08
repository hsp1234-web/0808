# -*- coding: utf-8 -*-
import os
from datetime import datetime
from faster_whisper import WhisperModel
import uuid

# 內部模組導入
from .logging_poc import get_poc_logger, TIMEZONE
from . import db_poc

# --- 常數定義 ---
# 為了穩定性和速度，POC 階段使用 base 模型
MODEL_SIZE = "base"

logger = get_poc_logger(__name__)

# 在模組加載時初始化模型，以供後續重複使用
# 這可以避免每次呼叫函式時都重新載入模型的開銷
try:
    logger.info(f"正在載入 Faster Whisper 模型: {MODEL_SIZE}...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    logger.info("模型載入成功。")
except Exception as e:
    logger.error(f"載入 Whisper 模型失敗: {e}", exc_info=True)
    model = None

def transcribe_audio(task_id: str, file_path: str) -> str | None:
    """
    使用 Faster Whisper 轉錄指定的音訊檔案。

    Args:
        task_id (str): 任務的唯一識別碼。
        file_path (str): 要轉錄的音訊檔案路徑。

    Returns:
        str | None: 若成功，返回轉錄後的完整文字；若失敗，返回 None。
    """
    if not model:
        error_msg = "Whisper 模型未被成功載入，無法進行轉錄。"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

    if not os.path.exists(file_path):
        error_msg = f"指定的檔案不存在: {file_path}"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

    started_at = datetime.now(TIMEZONE).isoformat()
    logger.info(f"[{task_id}] 開始轉錄檔案: {file_path}")
    db_poc.update_task_status(task_id, "transcribing", started_at=started_at)

    try:
        # 執行轉錄
        segments, info = model.transcribe(file_path, beam_size=5)

        logger.info(f"[{task_id}] 偵測到語言: {info.language} (機率: {info.language_probability:.2f})")

        full_text = "".join(segment.text for segment in segments)

        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.update_task_on_completion(task_id, "transcription_completed", finished_at)

        logger.info(f"[{task_id}] 檔案轉錄成功。")
        return full_text.strip()

    except Exception as e:
        error_msg = f"轉錄過程中發生未預期的錯誤: {e}"
        logger.error(f"[{task_id}] {error_msg}", exc_info=True)
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None

# 為了測試，需要導入 youtube_poc
from . import youtube_poc

if __name__ == '__main__':
    # --- 執行整合測試 ---
    print("--- 開始執行 transcriber_poc 模組整合測試 ---")

    downloaded_file_path = None
    if not model:
        print(f"!!! 測試失敗: Whisper 模型未能載入。")
    else:
        # 1. 先執行 youtube_poc 來獲取一個有效的音訊檔
        # 測試用的 URL (一個穩定的、高可用性的影片)
        TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley - Never Gonna Give You Up
        yt_task_id = f"poc-test-yt-{uuid.uuid4()}"
        now = datetime.now(TIMEZONE).isoformat()
        db_poc.create_task(yt_task_id, TEST_URL, now)
        print(f"建立 YouTube 下載任務: {yt_task_id}")

        downloaded_file_path = youtube_poc.process_youtube_video(yt_task_id, TEST_URL)

        if not downloaded_file_path or not os.path.exists(downloaded_file_path):
            print("!!! 測試前置步驟失敗: 無法成功下載 YouTube 影片作為測試檔案。")
            downloaded_file_path = None # 確保變數為 None
        else:
            print(f"成功下載測試檔案: {downloaded_file_path}")

            # 2. 在資料庫中建立一個新的轉錄任務
            transcribe_task_id = f"poc-test-transcribe-{uuid.uuid4()}"
            db_poc.create_task(transcribe_task_id, f"file://{downloaded_file_path}", now)
            print(f"在資料庫中建立了轉錄測試任務: {transcribe_task_id}")

            # 3. 執行轉錄函式
            print(f"正在使用檔案 '{downloaded_file_path}' 執行 transcribe_audio...")
            transcript = transcribe_audio(transcribe_task_id, downloaded_file_path)

            # 4. 驗證結果
            print("\n--- 驗證轉錄結果 ---")
            conn = db_poc.get_db_connection()
            task_data = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (transcribe_task_id,)).fetchone()
            conn.close()

            if task_data:
                print(f"資料庫狀態: {task_data['status']}")

                if task_data['status'] == 'transcription_completed' and transcript is not None:
                    print("轉錄成功！")
                    print(f"轉錄結果: '{transcript}'")
                    if transcript: # 檢查轉錄結果是否為非空字串
                         print("驗證成功: 轉錄內容非空。")
                    else:
                         print("!!! 驗證失敗: 轉錄內容為空。")
                else:
                    print("!!! 測試失敗，任務未成功完成。")
                    print(f"錯誤訊息: {task_data['error_message']}")
            else:
                print("!!! 驗證失敗: 在資料庫中找不到測試任務。")

    # 5. 清理下載的檔案
    if downloaded_file_path and os.path.exists(downloaded_file_path):
        os.remove(downloaded_file_path)
        print(f"\n已清理測試檔案: {downloaded_file_path}")

    print("\n--- transcriber_poc 模組測試結束 ---")
