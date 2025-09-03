# src/worker/worker.py
import time
import asyncio
import json
import httpx
import logging
import sys
import os
from pathlib import Path

# --- 修正模組匯入路徑 ---
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from db.client_v2 import get_client

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('worker')

# --- 常數設定 ---
API_PORT = os.environ.get("API_PORT", "8001")
API_SERVER_URL = f"http://127.0.0.1:{API_PORT}"
API_HEALTH_ENDPOINT = f"{API_SERVER_URL}/api/health"
API_NOTIFY_ENDPOINT = f"{API_SERVER_URL}/api/internal/notify_task_update"
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = ROOT_DIR / "uploads"

# --- DB 客戶端 ---
db_client = get_client()

async def run_subprocess_async(cmd: list, env: dict = None):
    """以非同步方式執行子程序並回傳結果。"""
    log.info(f"執行指令: {' '.join(map(str, cmd))}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    stdout, stderr = await process.communicate()

    decoded_stdout = stdout.decode('utf-8').strip()
    decoded_stderr = stderr.decode('utf-8').strip()

    if process.returncode != 0:
        log.error(f"子程序執行失敗，返回碼: {process.returncode}")
        log.error(f"  [STDOUT]: {decoded_stdout}")
        log.error(f"  [STDERR]: {decoded_stderr}")

    return process.returncode, decoded_stdout, decoded_stderr

async def process_transcription_task(task: dict):
    """處理單一轉錄任務的邏輯 (異步版本)"""
    task_id = task['task_id']
    log.info(f"開始處理轉錄任務: {task_id}")

    try:
        payload = json.loads(task['payload'])
        file_path = payload['input_file']
        model_size = payload.get('model_size', 'tiny')
        language = payload.get('language')
        beam_size = payload.get('beam_size', 5)

        output_dir = UPLOADS_DIR / "transcripts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file_path = output_dir / f"{task_id}.txt"

        is_mock_mode = os.environ.get("API_MODE", "real") == "mock"
        tool_script = "mock_transcriber.py" if is_mock_mode else "transcriber.py"
        tool_script_path = ROOT_DIR / "src" / "tools" / tool_script

        cmd = [
            sys.executable, str(tool_script_path),
            "--command=transcribe",
            f"--audio_file={file_path}",
            f"--output_file={output_file_path}",
            f"--model_size={model_size}",
        ]
        if language: cmd.append(f"--language={language}")
        cmd.append(f"--beam_size={beam_size}")

        returncode, stdout, stderr = await run_subprocess_async(cmd)

        if returncode == 0:
            final_transcript = output_file_path.read_text(encoding='utf-8').strip()
            media_url = f"/media/transcripts/{output_file_path.name}"
            final_result_obj = {
                "transcript": final_transcript,
                "transcript_path": media_url,
                "output_path": media_url
            }
            db_client.update_task_status(task_id, 'completed', json.dumps(final_result_obj))
            await notify_api_server(task_id, 'completed', final_result_obj)
        else:
            error_message = stderr or "轉錄失敗，無詳細錯誤訊息。"
            log.error(f"轉錄任務 {task_id} 失敗: {error_message}")
            error_payload = {'error': error_message}
            db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
            await notify_api_server(task_id, 'failed', error_payload)

    except Exception as e:
        log.error(f"處理轉錄任務 {task_id} 時發生嚴重錯誤: {e}", exc_info=True)
        error_payload = {'error': str(e)}
        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        await notify_api_server(task_id, 'failed', error_payload)

async def process_youtube_task(task: dict):
    """處理單一 YouTube 任務的邏輯 (異步版本)"""
    task_id = task['task_id']
    task_type = task['type']
    log.info(f"開始處理 YouTube 任務: {task_id} (類型: {task_type})")

    try:
        is_mock_mode = os.environ.get("API_MODE", "real") == "mock"
        payload = json.loads(task['payload'])
        download_result = {}

        if task_type in ['youtube_download', 'youtube_download_only']:
            url = payload['url']
            custom_filename = payload.get("custom_filename")
            download_type = payload.get("download_type", "audio")

            downloader_script = "mock_youtube_downloader.py" if is_mock_mode else "youtube_downloader.py"
            downloader_script_path = ROOT_DIR / "src" / "tools" / downloader_script
            cmd_dl = [sys.executable, str(downloader_script_path), "--url", url, "--output-dir", str(UPLOADS_DIR), "--download-type", download_type]
            if custom_filename: cmd_dl.extend(["--custom-filename", custom_filename])
            cookies_path = UPLOADS_DIR / "cookies.txt"
            if cookies_path.is_file(): cmd_dl.extend(["--cookies-file", str(cookies_path)])

            returncode_dl, stdout_dl, stderr_dl = await run_subprocess_async(cmd_dl)

            if returncode_dl != 0: raise RuntimeError(f"下載失敗: {stderr_dl or stdout_dl}")

            download_result = json.loads(stdout_dl)
            download_result['output_path'] = f"/media/{Path(download_result['output_path']).relative_to(UPLOADS_DIR).as_posix()}"

            if task_type == 'youtube_download_only':
                db_client.update_task_status(task_id, 'completed', json.dumps(download_result))
                await notify_api_server(task_id, 'completed', download_result)
                return

            db_client.update_task_status(task_id, 'completed', json.dumps(download_result))
            dependent_task_id = db_client.find_dependent_task(task_id)
            if not dependent_task_id: raise ValueError(f"找不到依賴於 {task_id} 的後續任務")

            process_task_info = db_client.get_task_status(dependent_task_id)
            payload = json.loads(process_task_info['payload'])
            payload['input_file'] = download_result['output_path']
            payload['video_title'] = download_result.get('video_title', '無標題影片')
            task_id = dependent_task_id
            task['type'] = 'gemini_process' # 更新當前任務類型以進入下一階段
            log.info(f"下載完成，繼續處理 AI 分析任務: {task_id}")

        if task['type'] == 'gemini_process':
            model, tasks_to_run, output_format, api_key = payload['model'], payload.get('tasks', 'summary,transcript'), payload.get('output_format', 'html'), payload.get('api_key')
            media_url = payload['input_file']
            audio_file_path = UPLOADS_DIR / Path(media_url.lstrip('/media/'))
            video_title = payload['video_title']

            processor_script = "mock_gemini_processor.py" if is_mock_mode else "gemini_processor.py"
            processor_script_path = ROOT_DIR / "src" / "tools" / processor_script
            report_output_dir = UPLOADS_DIR / "reports"
            report_output_dir.mkdir(parents=True, exist_ok=True)

            cmd_process = [
                sys.executable, str(processor_script_path),
                "--command=process", "--audio-file", str(audio_file_path), "--model", model,
                "--output-dir", str(report_output_dir), "--video-title", video_title,
                "--tasks", tasks_to_run, "--output-format", output_format
            ]
            proc_env = os.environ.copy()
            if api_key: proc_env["GOOGLE_API_KEY"] = api_key

            returncode_proc, stdout_proc, stderr_proc = await run_subprocess_async(cmd_process, env=proc_env)

            if returncode_proc != 0: raise RuntimeError(f"AI 分析失敗: {stderr_proc or stdout_proc}")

            process_result = json.loads(stdout_proc)
            for key in ["output_path", "html_report_path", "pdf_report_path"]:
                if key in process_result and process_result[key]:
                    process_result[key] = f"/media/{Path(process_result[key]).relative_to(UPLOADS_DIR).as_posix()}"

            db_client.update_task_status(task_id, 'completed', json.dumps(process_result))
            await notify_api_server(task_id, 'completed', process_result)

    except Exception as e:
        log.error(f"處理 YouTube 任務 {task_id} 時發生嚴重錯誤: {e}", exc_info=True)
        error_payload = {'error': str(e)}
        db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))
        await notify_api_server(task_id, 'failed', error_payload)

async def heartbeat_task():
    """定期向資料庫發送心跳，表明 Worker 處於活動狀態。"""
    log.info("❤️ 心跳任務已啟動，將每 10 秒回報一次狀態。")
    while True:
        try:
            # 使用 time.time() 獲取 Unix 時間戳
            current_timestamp = time.time()
            db_client.set_app_state("worker_last_heartbeat", str(current_timestamp))
            log.debug(f"❤️ 心跳已發送: {current_timestamp}")
        except Exception as e:
            log.error(f"❌ 發送心跳時發生錯誤: {e}", exc_info=True)
        # 等待 10 秒
        await asyncio.sleep(10)


async def notify_api_server(task_id: str, status: str, result: dict = None):
    """通知 API 伺服器任務已更新 (異步版本)"""
    try:
        log.info(f"正在通知 API 伺服器，任務 {task_id} 狀態為: {status}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                API_NOTIFY_ENDPOINT,
                json={"task_id": task_id, "status": status, "result": result},
                timeout=10
            )
            response.raise_for_status()
        log.info(f"成功通知 API 伺服器: {task_id}")
    except httpx.RequestError as e:
        log.error(f"通知 API 伺服器失敗: {e}")

async def main_loop():
    """工人的主迴圈，不斷輪詢並處理任務 (異步版本)"""
    log.info("✅ Worker 主迴圈已啟動，開始輪詢任務...")
    while True:
        task = db_client.fetch_and_lock_task()
        if task:
            try:
                log.info(f"領取到新任務: {task['task_id']}, 類型: {task['type']}")
                if task['type'] == 'transcribe':
                    await process_transcription_task(task)
                elif task['type'] in ['youtube_download', 'gemini_process', 'youtube_download_only']:
                    await process_youtube_task(task)
                else:
                    log.warning(f"未知的任務類型: {task['type']}，任務 {task['task_id']} 將被忽略。")
                    error_payload = {'error': f"未知的任務類型: {task['type']}"}
                    db_client.update_task_status(task['task_id'], 'failed', json.dumps(error_payload))
                    await notify_api_server(task['task_id'], 'failed', error_payload)
            except Exception as e:
                log.error(f"處理任務 {task['task_id']} 時發生未預期的錯誤: {e}", exc_info=True)
                error_payload = {'error': f'Worker error: {e}'}
                db_client.update_task_status(task['task_id'], 'failed', json.dumps(error_payload))
                await notify_api_server(task['task_id'], 'failed', error_payload)
        else:
            await asyncio.sleep(2)

async def main():
    # 在新架構中，Orchestrator 負責確保所有服務就緒。
    # Worker 可以直接開始其核心任務：發送心跳和處理任務。
    log.info("Worker 直接啟動，不再執行健康握手。")
    loop = asyncio.get_running_loop()
    loop.create_task(heartbeat_task())
    await main_loop()

if __name__ == "__main__":
    # 安裝 uvloop (如果可用) 以獲得更佳效能
    try:
        import uvloop
        uvloop.install()
        log.info("uvloop 已安裝並啟用。")
    except ImportError:
        log.info("uvloop 未安裝，將使用標準 asyncio 事件迴圈。")
        pass
    asyncio.run(main())
