# -*- coding: utf-8 -*-
import os
import subprocess
import hashlib
from datetime import datetime
import uuid

# 內部模組導入
from .logging_poc import get_poc_logger, TIMEZONE
from . import db_poc

# --- 常數定義 ---
TMP_DIR = "uploads_poc/tmp"
FILES_DIR = "uploads_poc/files"
DOWNLOAD_TIMEOUT = 300  # 下載超時時間（秒）

logger = get_poc_logger(__name__)

def _calculate_sha256(filepath: str) -> str:
    """計算檔案的 SHA256 雜湊值。"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def process_youtube_video(task_id: str, url: str) -> str | None:
    """
    處理單一 YouTube 影片下載任務。

    Args:
        task_id (str): 任務的唯一識別碼。
        url (str): YouTube 影片的 URL。

    Returns:
        str | None: 若成功，返回最終檔案的路徑；若失敗，返回 None。
    """
    started_at = datetime.now(TIMEZONE).isoformat()
    logger.info(f"[{task_id}] 開始處理 YouTube 影片下載，URL: {url}")
    db_poc.update_task_status(task_id, "downloading", started_at=started_at)

    tmp_filename = f"{task_id}.%(ext)s"
    tmp_filepath_template = os.path.join(TMP_DIR, tmp_filename)

    # yt-dlp 命令
    # -f bestaudio[ext=m4a]/bestaudio: 選擇 m4a 或最佳音訊
    # -x: 提取音訊
    # --audio-format mp3: 轉換為 mp3
    command = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio",
        "-x",
        "--audio-format", "mp3",
        "--output", tmp_filepath_template,
        url,
    ]

    try:
        logger.info(f"[{task_id}] 執行 yt-dlp 命令: {' '.join(command)}")

        # 執行下載，設定超時
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=DOWNLOAD_TIMEOUT,
            encoding='utf-8',
            check=True  # 如果返回非零碼，則拋出 CalledProcessError
        )
        logger.info(f"[{task_id}] yt-dlp 下載成功。標準輸出:\n{result.stdout}")

        # 找到實際下載的檔案名稱（因為副檔名是動態的）
        downloaded_file = None
        for file in os.listdir(TMP_DIR):
            if file.startswith(task_id) and file.endswith(".mp3"):
                downloaded_file = os.path.join(TMP_DIR, file)
                break

        if not downloaded_file:
            raise FileNotFoundError("下載後在臨時目錄中找不到預期的 .mp3 檔案。")

        # 2. 計算雜湊值
        logger.info(f"[{task_id}] 計算檔案 '{downloaded_file}' 的 SHA256 雜湊值...")
        file_hash = _calculate_sha256(downloaded_file)
        logger.info(f"[{task_id}] 計算出的雜湊值為: {file_hash}")

        # 3. 原子化重命名
        file_extension = os.path.splitext(downloaded_file)[1]
        final_filename = f"{file_hash}{file_extension}"
        final_filepath = os.path.join(FILES_DIR, final_filename)

        logger.info(f"[{task_id}] 原子化移動檔案: '{downloaded_file}' -> '{final_filepath}'")
        os.rename(downloaded_file, final_filepath)

        # 4. 更新資料庫
        db_poc.update_task_file_hash(task_id, file_hash)
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.update_task_on_completion(task_id, "download_completed", finished_at)

        logger.info(f"[{task_id}] YouTube 影片下載任務成功完成。")
        return final_filepath

    except subprocess.TimeoutExpired:
        error_msg = f"下載超時（超過 {DOWNLOAD_TIMEOUT} 秒）。"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None
    except subprocess.CalledProcessError as e:
        error_msg = f"yt-dlp 執行失敗，返回碼 {e.returncode}。\n標準錯誤:\n{e.stderr}"
        logger.error(f"[{task_id}] {error_msg}")
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None
    except Exception as e:
        error_msg = f"處理過程中發生未預期的錯誤: {e}"
        logger.error(f"[{task_id}] {error_msg}", exc_info=True)
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        return None


if __name__ == '__main__':
    # --- 執行測試 ---
    print("--- 開始執行 youtube_poc 模組測試 ---")

    # 測試用的 URL (一個簡短的、無版權的影片)
    TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # Rick Astley - Never Gonna Give You Up

    # 1. 在資料庫中建立一個測試任務
    test_task_id = f"poc-test-{uuid.uuid4()}"
    now = datetime.now(TIMEZONE).isoformat()
    db_poc.create_task(test_task_id, TEST_URL, now)
    print(f"在資料庫中建立了測試任務: {test_task_id}")

    # 2. 執行處理函式
    print(f"正在使用 URL '{TEST_URL}' 執行 process_youtube_video...")
    final_path = process_youtube_video(test_task_id, TEST_URL)

    # 3. 驗證結果
    print("\n--- 驗證結果 ---")
    conn = db_poc.get_db_connection()
    task_data = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (test_task_id,)).fetchone()
    conn.close()

    if task_data:
        print(f"資料庫狀態: {task_data['status']}")
        print(f"檔案雜湊值: {task_data['file_hash']}")
        print(f"錯誤訊息: {task_data['error_message']}")

        if task_data['status'] == 'download_completed' and final_path:
            print(f"檔案已成功儲存至: {final_path}")
            if os.path.exists(final_path):
                print("驗證成功: 最終檔案存在於指定路徑。")
                # 清理測試檔案
                os.remove(final_path)
                print(f"已清理測試檔案: {final_path}")
            else:
                print("!!! 驗證失敗: 最終檔案不存在。")
        else:
            print("!!! 測試失敗，任務未成功完成。")
    else:
        print("!!! 驗證失敗: 在資料庫中找不到測試任務。")

    print("\n--- youtube_poc 模組測試結束 ---")
