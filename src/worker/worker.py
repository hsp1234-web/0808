# src/worker/worker.py
import time
import subprocess
import json
import requests
import logging
import sys
import os
from pathlib import Path

# --- 修正模組匯入路徑 ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from db.client import get_client

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('worker')

# --- 常數設定 ---
API_SERVER_URL = "http://127.0.0.1:8001" # 根據 circus.ini.template 中的設定
API_HEALTH_ENDPOINT = f"{API_SERVER_URL}/api/health"
API_NOTIFY_ENDPOINT = f"{API_SERVER_URL}/api/internal/notify_task_update"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = ROOT_DIR / "uploads"

# --- DB 客戶端 ---
db_client = get_client()

def process_transcription_task(task: dict):
    """處理單一轉錄任務的邏輯"""
    task_id = task['task_id']
    log.info(f"開始處理轉錄任務: {task_id}")

    try:
        payload = json.loads(task['payload'])
        file_path = payload['input_file']
        original_filename = payload.get('original_filename', Path(file_path).name)
        model_size = payload.get('model_size', 'tiny')
        language = payload.get('language')
        beam_size = payload.get('beam_size', 5)

        output_dir = UPLOADS_DIR / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file_path = output_dir / f"{task_id}.txt"

        # 根據環境變數決定是否使用模擬器
        is_mock_mode = os.environ.get("API_MODE", "real") == "mock"
        force_mock = os.environ.get("FORCE_MOCK_TRANSCRIBER") == "true"
        tool_script_path = ROOT_DIR / "src" / "tools" / ("mock_transcriber.py" if is_mock_mode or force_mock else "transcriber.py")

        cmd = [
            sys.executable, str(tool_script_path),
            "--command=transcribe",
            f"--audio_file={file_path}",
            f"--output_file={output_file_path}",
            f"--model_size={model_size}",
        ]
        if language:
            cmd.append(f"--language={language}")
        cmd.append(f"--beam_size={beam_size}")

        log.info(f"執行轉錄指令: {' '.join(map(str, cmd))}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

        if result.returncode == 0:
            final_transcript = output_file_path.read_text(encoding='utf-8').strip()
            # 將檔案系統路徑轉換為可存取的 URL
            media_url = f"/media/transcripts/{output_file_path.name}"
            final_result_obj = {
                "transcript": final_transcript,
                "transcript_path": media_url,
                "output_path": media_url
            }
            db_client.update_task_status(task_id, 'completed', json.dumps(final_result_obj))
            notify_api_server(task_id, 'completed', final_result_obj)
        else:
            error_message = result.stderr or "轉錄失敗，無詳細錯誤訊息。"
            log.error(f"轉錄任務 {task_id} 失敗: {error_message}")
            error_payload = {'error': error_message}
            db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
            notify_api_server(task_id, 'failed', error_payload)

    except Exception as e:
        log.error(f"處理轉錄任務 {task_id} 時發生嚴重錯誤: {e}", exc_info=True)
        error_payload = {'error': str(e)}
        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        notify_api_server(task_id, 'failed', error_payload)


def process_youtube_task(task: dict):
    """處理單一 YouTube 任務的邏輯 (下載或分析)"""
    task_id = task['task_id']
    task_type = task['type']
    log.info(f"開始處理 YouTube 任務: {task_id} (類型: {task_type})")

    try:
        is_mock_mode = os.environ.get("API_MODE", "real") == "mock"
        payload = json.loads(task['payload'])

        # --- 下載階段 ---
        if task_type in ['youtube_download', 'youtube_download_only']:
            url = payload['url']
            custom_filename = payload.get("custom_filename")
            download_type = payload.get("download_type", "audio")

            downloader_script_path = ROOT_DIR / "src" / "tools" / ("mock_youtube_downloader.py" if is_mock_mode else "youtube_downloader.py")
            cmd_dl = [sys.executable, str(downloader_script_path), "--url", url, "--output-dir", str(UPLOADS_DIR), "--download-type", download_type]
            if custom_filename:
                cmd_dl.extend(["--custom-filename", custom_filename])

            cookies_path = UPLOADS_DIR / "cookies.txt"
            if cookies_path.is_file():
                cmd_dl.extend(["--cookies-file", str(cookies_path)])

            log.info(f"執行下載指令: {' '.join(cmd_dl)}")
            result_dl = subprocess.run(cmd_dl, capture_output=True, text=True, encoding='utf-8')

            if result_dl.returncode != 0:
                raise RuntimeError(f"下載失敗: {result_dl.stderr or result_dl.stdout}")

            download_result = json.loads(result_dl.stdout)
            # 將路徑轉換為 URL
            download_result['output_path'] = f"/media/{Path(download_result['output_path']).relative_to(UPLOADS_DIR).as_posix()}"

            if task_type == 'youtube_download_only':
                db_client.update_task_status(task_id, 'completed', json.dumps(download_result))
                notify_api_server(task_id, 'completed', download_result)
                return # 任務結束

            # 如果是鏈式任務，更新下載任務狀態，並觸發後續
            db_client.update_task_status(task_id, 'completed', json.dumps(download_result))
            # 注意：這裡不通知，因為鏈還沒結束

            dependent_task_id = db_client.find_dependent_task(task_id)
            if not dependent_task_id:
                raise ValueError(f"找不到依賴於 {task_id} 的後續任務")

            # 將後續任務的 payload 注入到下一個處理階段
            process_task_info = db_client.get_task_status(dependent_task_id)
            payload = json.loads(process_task_info['payload'])
            payload['input_file'] = download_result['output_path'] # 使用 URL 化的路徑
            payload['video_title'] = download_result.get('video_title', '無標題影片')
            task_id = dependent_task_id # 將當前 task_id 切換到分析任務
            log.info(f"下載完成，繼續處理 AI 分析任務: {task_id}")


        # --- AI 分析階段 ---
        if task['type'] == 'gemini_process':
            model = payload['model']
            tasks_to_run = payload.get('tasks', 'summary,transcript')
            output_format = payload.get('output_format', 'html')
            api_key = payload.get('api_key')
            # 從 payload 中獲取下載階段傳來的檔案路徑和標題
            media_url = payload['input_file']
            # 將 URL 轉回檔案系統路徑
            audio_file_path = UPLOADS_DIR / Path(media_url.lstrip('/media/'))
            video_title = payload['video_title']

            processor_script_path = ROOT_DIR / "src" / "tools" / ("mock_gemini_processor.py" if is_mock_mode else "gemini_processor.py")
            report_output_dir = UPLOADS_DIR / "reports"
            report_output_dir.mkdir(parents=True, exist_ok=True)

            cmd_process = [
                sys.executable, str(processor_script_path),
                "--command=process",
                "--audio-file", str(audio_file_path),
                "--model", model,
                "--output-dir", str(report_output_dir),
                "--video-title", video_title,
                "--tasks", tasks_to_run,
                "--output-format", output_format
            ]

            proc_env = os.environ.copy()
            if api_key:
                proc_env["GOOGLE_API_KEY"] = api_key

            log.info(f"執行 AI 分析指令: {' '.join(cmd_process)}")
            result_process = subprocess.run(cmd_process, capture_output=True, text=True, encoding='utf-8', env=proc_env)

            if result_process.returncode != 0:
                 raise RuntimeError(f"AI 分析失敗: {result_process.stderr or result_process.stdout}")

            process_result = json.loads(result_process.stdout)
            # 將所有結果路徑轉換為 URL
            for key in ["output_path", "html_report_path", "pdf_report_path"]:
                 if key in process_result and process_result[key]:
                    process_result[key] = f"/media/{Path(process_result[key]).relative_to(UPLOADS_DIR).as_posix()}"

            db_client.update_task_status(task_id, 'completed', json.dumps(process_result))
            notify_api_server(task_id, 'completed', process_result)

    except Exception as e:
        log.error(f"處理 YouTube 任務 {task_id} 時發生嚴重錯誤: {e}", exc_info=True)
        error_payload = {'error': str(e)}
        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        notify_api_server(task_id, 'failed', error_payload)


def notify_api_server(task_id: str, status: str, result: dict = None):
    """通知 API 伺服器任務已更新"""
    try:
        log.info(f"正在通知 API 伺服器，任務 {task_id} 狀態為: {status}")
        response = requests.post(
            API_NOTIFY_ENDPOINT,
            json={"task_id": task_id, "status": status, "result": result},
            timeout=10 # 設定超時
        )
        response.raise_for_status() # 如果狀態碼不是 2xx，則引發例外
        log.info(f"成功通知 API 伺服器: {task_id}")
    except requests.exceptions.RequestException as e:
        log.error(f"通知 API 伺服器失敗: {e}")

def main_loop():
    """工人的主迴圈，不斷輪詢並處理任務。"""
    log.info("✅ Worker 主迴圈已啟動，開始輪詢任務...")
    while True:
        # **注意**: fetch_and_lock_task 需要被修改，以尋找 'pending' 狀態的任務
        task = db_client.fetch_and_lock_task()
        if task:
            try:
                log.info(f"領取到新任務: {task['task_id']}, 類型: {task['type']}")
                if task['type'] == 'transcribe':
                    process_transcription_task(task)
                elif task['type'] in ['youtube_download', 'gemini_process', 'youtube_download_only']:
                    process_youtube_task(task)
                else:
                    log.warning(f"未知的任務類型: {task['type']}，任務 {task['task_id']} 將被忽略。")
                    db_client.update_task_status(task['task_id'], 'failed', json.dumps({'error': f"未知的任務類型: {task['type']}"}))
                    notify_api_server(task['task_id'], 'failed', {'error': f"未知的任務類型: {task['type']}"})

            except Exception as e:
                log.error(f"處理任務 {task['task_id']} 時發生未預期的錯誤: {e}", exc_info=True)
                error_payload = {'error': f'Worker error: {e}'}
                db_client.update_task_status(task['task_id'], 'failed', json.dumps(error_payload))
                notify_api_server(task['task_id'], 'failed', error_payload)
        else:
            # 如果佇列為空，等待一段時間
            time.sleep(2)

def health_handshake():
    """
    健康握手協議。在啟動主迴圈前，確認 API 伺服器已準備就緒。
    """
    log.info("🤝 開始與 API 伺服器進行健康握手...")
    max_retries = 30
    retry_delay = 2 # 秒
    for attempt in range(max_retries):
        try:
            response = requests.get(API_HEALTH_ENDPOINT, timeout=5)
            if response.status_code == 200:
                log.info("✅ 健康握手成功！API 伺服器已準備就緒。")
                return True
        except requests.ConnectionError:
            log.warning(f"連接 API 伺服器失敗，將在 {retry_delay} 秒後重試... ({attempt + 1}/{max_retries})")
        except Exception as e:
            log.error(f"健康握手時發生未預期錯誤: {e}")

        time.sleep(retry_delay)

    log.critical("❌ 健康握手失敗，無法在指定時間內連接到 API 伺服器。Worker 將退出。")
    return False

if __name__ == "__main__":
    if health_handshake():
        main_loop()
