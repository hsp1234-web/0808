# worker.py
import time
import logging
import json
import subprocess
import sys
import argparse
import requests
import os
import shutil
from pathlib import Path

# 將專案根目錄加入 sys.path
# 因為此檔案現在位於 src/tasks/ 中，所以根目錄是其上上層目錄
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
# sys.path hack 不再需要，因為我們現在使用 `pip install -e .`
# sys.path.insert(0, str(ROOT_DIR))

# JULES'S REFACTOR: Use the database client instead of direct access
# from db import database
from db.client import get_client

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('worker')

def setup_database_logging():
    """設定資料庫日誌處理器。"""
    try:
        from db.log_handler import DatabaseLogHandler
        root_logger = logging.getLogger()
        if not any(isinstance(h, DatabaseLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(DatabaseLogHandler(source='worker'))
            log.info("資料庫日誌處理器設定完成 (source: worker)。")
    except Exception as e:
        log.error(f"整合資料庫日誌時發生錯誤: {e}", exc_info=True)

# --- 路徑設定 ---
TOOLS_DIR = ROOT_DIR / "src" / "tools"
UPLOADS_DIR = ROOT_DIR / "uploads"
TRANSCRIPTS_DIR = ROOT_DIR / "transcripts" # 舊路徑，可考慮未來重構
# 確保上傳目錄存在
UPLOADS_DIR.mkdir(exist_ok=True)


# --- DB 客戶端 ---
db_client = get_client()

# --- 輔助函式 ---

def convert_to_media_url(absolute_path_str: str) -> str:
    """將絕對檔案系統路徑轉換為可公開存取的 /media URL。"""
    try:
        absolute_path = Path(absolute_path_str)
        # Find the path relative to the UPLOADS_DIR
        relative_path = absolute_path.relative_to(UPLOADS_DIR)
        # Join with /media/ and convert backslashes to forward slashes for URL
        return f"/media/{relative_path.as_posix()}"
    except (ValueError, TypeError):
        log.warning(f"無法將路徑 {absolute_path_str} 轉換為媒體 URL。回傳原始路徑。")
        return absolute_path_str

def convert_media_url_to_path(media_url: str) -> Path:
    """將 /media URL 轉換回伺服器上的絕對檔案系統路徑。"""
    if not media_url.startswith('/media/'):
        raise ValueError("無效的媒體 URL，必須以 /media/ 開頭。")
    # 移除 '/media/' 前綴並與上傳目錄合併
    relative_path = media_url.lstrip('/media/')
    return UPLOADS_DIR / relative_path

def notify_api_server(task_id: str, status: str, result: dict):
    """通知 API Server 任務狀態已更新，以便廣播給前端。"""
    try:
        # 注意：這裡假設 api_server 在 42649 port 上運行 (根據 circus.ini)
        notify_url = "http://127.0.0.1:42649/api/internal/notify_task_update"
        frontend_payload = {
            "task_id": task_id,
            "status": status,
            "result": result
        }
        requests.post(notify_url, json=frontend_payload, timeout=5)
        log.info(f"✅ 已成功發送 {status} 通知給 API Server: {task_id}")
    except requests.exceptions.RequestException as e:
        log.error(f"❌ 發送 {status} 通知給 API Server 失敗: {e}")

def process_download_task(task: dict, use_mock: bool):
    """處理模型下載任務。"""
    task_id = task['task_id']
    payload = json.loads(task['payload'])
    model_size = payload['model_size']
    log.info(f"🚀 開始處理 'download' 任務: {task_id} for model '{model_size}'")

    # 在模擬模式下，我們也假裝下載
    if use_mock:
        log.info("(模擬) 假裝下載模型...")
        time.sleep(3)
        db_client.update_task_status(task_id, 'completed', json.dumps({"message": "模型已成功下載 (模擬)"}))
        return

    # 真實模式下，呼叫工具的 download 命令
    tool_script_path = TOOLS_DIR / "transcriber.py"
    command = [sys.executable, str(tool_script_path), f"--command=download", f"--model_size={model_size}"]

    # 我們可以像轉錄一樣監聽進度，但 download_model 目前只在結束時輸出一次
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

    for line in process.stdout:
        try:
            progress_data = json.loads(line)
            db_client.update_task_progress(task_id, progress_data.get("progress", 0), progress_data.get("log", ""))
        except json.JSONDecodeError:
            log.info(f"[下載工具 stdout] {line.strip()}")

    process.wait()
    if process.returncode == 0:
        db_client.update_task_status(task_id, 'completed', json.dumps({"message": f"模型 {model_size} 已成功下載"}))
    else:
        log.error(f"❌ 下載模型 {model_size} 失敗。")
        db_client.update_task_status(task_id, 'failed', json.dumps({"error": f"下載模型 {model_size} 失敗"}))


def process_transcription_task(task: dict, use_mock: bool):
    """處理音訊轉錄任務。"""
    task_id = task['task_id']
    log.info(f"🚀 開始處理 'transcribe' 任務: {task_id}")
    try:
        payload = json.loads(task['payload'])
        input_file = Path(payload['input_file'])
        model_size = payload.get('model_size', 'tiny')
        language = payload.get('language')

        if not input_file.exists():
            raise FileNotFoundError(f"輸入檔案不存在: {input_file}")

        # 1. 決定要使用的工具
        tool_script_name = "mock_transcriber.py" if use_mock else "transcriber.py"
        tool_script_path = TOOLS_DIR / tool_script_name
        if not tool_script_path.exists():
             raise FileNotFoundError(f"工具腳本不存在: {tool_script_path}")

        # 2. 準備輸出路徑
        TRANSCRIPTS_DIR.mkdir(exist_ok=True)
        output_file = TRANSCRIPTS_DIR / f"{task_id}.txt"

        # 3. 構建並執行命令
        command = [
            sys.executable,
            str(tool_script_path),
            f"--command=transcribe", # 明確指定命令
            f"--audio_file={input_file}",
            f"--output_file={output_file}",
            f"--model_size={model_size}"
        ]
        if language:
            command.append(f"--language={language}")

        log.info(f"🔧 執行命令: {' '.join(command)}")

        # 改用 Popen 進行非阻塞式讀取
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

        # 4. 即時讀取 stdout 來更新進度
        full_stdout = []
        full_stderr = []

        # 使用緒來避免阻塞
        def read_stderr():
            for line in process.stderr:
                full_stderr.append(line)
                log.warning(f"[工具 stderr] {line.strip()}")

        import threading
        stderr_thread = threading.Thread(target=read_stderr)
        stderr_thread.start()

        for line in process.stdout:
            full_stdout.append(line)
            try:
                # 解析 JSON 進度
                progress_data = json.loads(line)
                progress = progress_data.get("progress")
                text = progress_data.get("text")
                if progress is not None:
                    log.info(f"📈 任務 {task_id} 進度: {progress}% - {text[:30]}...")
                    db_client.update_task_progress(task_id, progress, text)
            except json.JSONDecodeError:
                # 不是 JSON 格式的日誌，直接印出
                log.info(f"[工具 stdout] {line.strip()}")

        process.wait()
        stderr_thread.join()

        # 5. 處理最終結果
        if process.returncode == 0:
            log.info(f"✅ 工具成功完成任務: {task_id}")
            final_transcript = output_file.read_text(encoding='utf-8').strip()
            result_obj = {
                "transcript": final_transcript,
                "transcript_path": str(output_file), # 新增此行，為下載 API 提供路徑
                "tool_stdout": "".join(full_stdout),
            }
            db_client.update_task_status(task_id, 'completed', json.dumps(result_obj))
            log.info(f"✅ 任務 {task_id} 狀態已更新至資料庫。")

            # 步驟 6: 通知 API Server 任務已完成
            notify_api_server(task_id, 'completed', result_obj)

        else:
            log.error(f"❌ 工具執行任務失敗: {task_id}。返回碼: {process.returncode}")
            error_message = "".join(full_stderr) or "".join(full_stdout) or "未知錯誤"
            result_obj = {
                "error": error_message,
                "tool_stdout": "".join(full_stdout),
                "tool_stderr": "".join(full_stderr)
            }
            db_client.update_task_status(task_id, 'failed', json.dumps(result_obj))
            notify_api_server(task_id, 'failed', result_obj)

    except Exception as e:
        log.critical(f"💥 處理任務 {task_id} 時發生未預期的嚴重錯誤: {e}", exc_info=True)
        result_obj = {"error": str(e)}
        db_client.update_task_status(task_id, 'failed', json.dumps(result_obj))
        notify_api_server(task_id, 'failed', result_obj)


def process_youtube_chain_task(task: dict, use_mock: bool):
    """
    處理 YouTube 下載和 AI 分析任務鏈。
    這將取代 api_server.py 中的 thread-based 方法。
    """
    task_id = task['task_id']
    task_type = task.get('type')
    log.info(f"🚀 開始處理 '{task_type}' 任務: {task_id}")

    # --- 步驟 1: 決定工作目錄 ---
    # 對於 gemini_process 任務，它重複使用其父任務的目錄
    parent_task_id = task.get('depends_on')
    work_dir_id = parent_task_id if parent_task_id else task_id
    work_dir = UPLOADS_DIR / work_dir_id
    work_dir.mkdir(exist_ok=True)
    log.info(f"📁 任務 {task_id} 將使用工作目錄: {work_dir}")


    try:
        payload = json.loads(task['payload'])
        # --- 步驟 2: 根據任務類型執行對應的工具 ---

        if task_type in ['youtube_download', 'youtube_download_only']:
            url = payload.get('url')
            if not url:
                raise ValueError("任務 payload 中缺少 'url'")

            # 準備 downloader 指令
            tool_script = TOOLS_DIR / ("mock_youtube_downloader.py" if use_mock else "youtube_downloader.py")
            cmd = [
                sys.executable, str(tool_script),
                "--url", url,
                "--output-dir", str(work_dir), # 使用隔離目錄
                "--download-type", payload.get("download_type", "audio")
            ]
            if payload.get("custom_filename"):
                cmd.extend(["--custom-filename", payload.get("custom_filename")])

            cookies_path = UPLOADS_DIR / "cookies.txt"
            if cookies_path.is_file():
                cmd.extend(["--cookies-file", str(cookies_path)])

            log.info(f"🔧 執行下載指令: {' '.join(cmd)}")
            process = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')

            result_data = json.loads(process.stdout)
            if result_data.get("status") == "failed":
                raise RuntimeError(result_data.get("error", "下載器回報了一個未知的錯誤"))

            # 將結果中的檔案路徑轉換為可公開存取的 URL
            for key in ["output_path", "html_report_path", "pdf_report_path"]:
                if key in result_data and result_data[key]:
                    result_data[key] = convert_to_media_url(result_data[key])

            db_client.update_task_status(task_id, 'completed', json.dumps(result_data))
            notify_api_server(task_id, 'completed', result_data)

        elif task_type == 'gemini_process':
            if not parent_task_id:
                raise ValueError("gemini_process 任務必須依賴於一個下載任務 ('depends_on' 欄位缺失)")

            # 獲取父任務的結果
            parent_task_info = db_client.get_task_status(parent_task_id)
            if not parent_task_info or parent_task_info.get('status') != 'completed':
                raise RuntimeError(f"父任務 {parent_task_id} 尚未成功完成，無法繼續。")

            parent_result = json.loads(parent_task_info.get('result', '{}'))
            media_url = parent_result.get('output_path')
            if not media_url:
                raise ValueError(f"父任務 {parent_task_id} 的結果中找不到 'output_path'")

            media_file_path = convert_media_url_to_path(media_url)
            if not media_file_path.exists():
                raise FileNotFoundError(f"找不到 Gemini 分析所需的媒體檔案: {media_file_path}")

            # 準備 processor 指令
            tool_script = TOOLS_DIR / ("mock_gemini_processor.py" if use_mock else "gemini_processor.py")
            cmd = [
                sys.executable, str(tool_script),
                "--command", "process",
                "--audio-file", str(media_file_path),
                "--output-dir", str(work_dir), # 報告也輸出到同一個隔離目錄
                "--model", payload.get("model"),
                "--video-title", parent_result.get("video_title", "無標題"),
                "--tasks", payload.get("tasks", "summary,transcript"),
                "--output-format", payload.get("output_format", "html")
            ]

            log.info(f"🔧 執行 Gemini 分析指令: {' '.join(cmd)}")
            # 注意：gemini_processor.py 可能會將進度更新寫入 stderr
            process = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')

            result_data = json.loads(process.stdout)
            if result_data.get("status") == "failed":
                raise RuntimeError(result_data.get("error", "Gemini 分析器回報了一個未知的錯誤"))

            # 將結果中的檔案路徑轉換為可公開存取的 URL
            for key in ["output_path", "html_report_path", "pdf_report_path"]:
                if key in result_data and result_data[key]:
                    result_data[key] = convert_to_media_url(result_data[key])

            db_client.update_task_status(task_id, 'completed', json.dumps(result_data))
            notify_api_server(task_id, 'completed', result_data)

        else:
            raise ValueError(f"在 process_youtube_chain_task 中遇到未知的任務類型: {task_type}")

    except (subprocess.CalledProcessError, RuntimeError, ValueError, FileNotFoundError) as e:
        log.error(f"❌ 處理任務 {task_id} ({task_type}) 失敗: {e}")
        error_message = str(e)
        if isinstance(e, subprocess.CalledProcessError):
            error_message = e.stderr or "yt-dlp 執行失敗且未提供 stderr。"

        # 嘗試從錯誤訊息中解析 JSON
        try:
            error_payload = json.loads(error_message)
        except json.JSONDecodeError:
            error_payload = {"error": error_message}

        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        notify_api_server(task_id, 'failed', error_payload)

    except Exception as e:
        log.critical(f"💥 處理任務 {task_id} 時發生未預期的嚴重錯誤: {e}", exc_info=True)
        error_payload = {"error": f"Worker 內部嚴重錯誤: {e}"}
        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        notify_api_server(task_id, 'failed', error_payload)

    finally:
        # --- 步驟 3: 清理隔離目錄 ---
        # 清理只應在任務鏈的最後一個任務完成後進行。
        task_is_final_in_chain = task_type in ['youtube_download_only', 'gemini_process']

        if task_is_final_in_chain:
            # work_dir 是根據 parent_task_id 或 task_id 決定的，所以路徑是正確的
            if work_dir.exists():
                try:
                    shutil.rmtree(work_dir)
                    log.info(f"🗑️ 已成功清理任務鏈的隔離目錄: {work_dir}")
                except Exception as e:
                    log.error(f"清理隔離目錄 {work_dir} 時發生錯誤: {e}", exc_info=True)
            else:
                log.warning(f"想要清理的目錄 {work_dir} 不存在，可能已被提前清理。")
        else:
            log.info(f"ℹ️ 任務 {task_id} ({task_type}) 不是鏈的終點，跳過清理步驟。")


def process_task(task: dict, use_mock: bool):
    """
    根據任務類型分派到不同的處理函式。
    """
    task_type = task.get('type', 'transcribe') # 預設為舊的轉錄任務
    if task_type == 'download':
        process_download_task(task, use_mock)
    elif task_type == 'transcribe':
        process_transcription_task(task, use_mock)
    elif task_type in ['youtube_download', 'youtube_download_only', 'gemini_process']:
        process_youtube_chain_task(task, use_mock)
    else:
        log.error(f"❌ 未知的任務類型: '{task_type}' (Task ID: {task['task_id']})")
        db_client.update_task_status(task['task_id'], 'failed', json.dumps({"error": f"未知的任務類型: {task_type}"}))

def main_loop(use_mock: bool, poll_interval: int):
    """
    工人的主迴圈，持續從佇列中拉取並處理任務。
    """
    log.info(f"🤖 Worker 已啟動。模式: {'模擬 (Mock)' if use_mock else '真實 (Real)'}。查詢間隔: {poll_interval} 秒。")
    try:
        while True:
            task = db_client.fetch_and_lock_task()
            if task:
                process_task(task, use_mock)
            else:
                # 佇列為空，稍作等待
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        log.info("🛑 收到中斷信號，Worker 正在關閉...")
    except Exception as e:
        log.critical(f"🔥 Worker 主迴圈發生致命錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="背景工作處理器。")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="如果設置此旗標，則使用 mock_transcriber.py 進行測試。"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="當佇列為空時，輪詢資料庫的間隔時間（秒）。"
    )
    args = parser.parse_args()

    # JULES'S REFACTOR: The worker no longer initializes the database directly.
    # The db_manager service is responsible for this.
    # database.initialize_database()

    # 然後設定日誌
    setup_database_logging()

    main_loop(args.mock, args.poll_interval)
