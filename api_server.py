# api_server.py
import uuid
import shutil
import logging
import json
import subprocess
import sys
import threading
import asyncio
import os
import time
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Dict, List
from pydantic import BaseModel
import argparse

from db.client import get_client

os.environ['TZ'] = 'Asia/Taipei'
if sys.platform != 'win32':
    time.tzset()

cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("--mock", action="store_true", help="啟用模擬模式")
cli_args, _ = cli_parser.parse_known_args()
IS_MOCK_MODE = cli_args.mock

ROOT_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
log = logging.getLogger('api_server')

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast_json(self, data: dict):
        for connection in self.active_connections:
            await connection.send_json(data)

manager = ConnectionManager()
db_client = get_client()
app = FastAPI(title="音訊轉錄儀 API", version="3.2")
app.mount("/static", StaticFiles(directory=ROOT_DIR / "static"), name="static")

GEMINI_API_KEY: Optional[str] = None

class TranscriptionRequest(BaseModel):
    file_path: str
    model_size: str
    language: Optional[str] = None
    beam_size: int = 5

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return HTMLResponse(content=(ROOT_DIR / "static" / "mp3.html").read_text(encoding="utf-8"))

def check_model_exists(model_size: str) -> bool:
    tool_script = "tools/mock_transcriber.py" if IS_MOCK_MODE else "tools/transcriber.py"
    cmd = [sys.executable, tool_script, "--command=check", f"--model_size={model_size}"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip().lower() == "exists"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

@app.post("/api/transcribe", status_code=202)
async def create_transcription_task(request: Request, file: Optional[UploadFile] = File(None), model_size: Optional[str] = Form(None), language: Optional[str] = Form(None), beam_size: Optional[int] = Form(None)):
    saved_file_path_str = ""
    display_filename = ""
    task_model_size = ""
    task_language = ""
    task_beam_size = 5

    content_type = request.headers.get('content-type', '')
    if 'application/json' in content_type:
        try:
            body = await request.json()
            req_data = TranscriptionRequest(**body)
            file_path_obj = Path(req_data.file_path).resolve()
            if UPLOADS_DIR.resolve() not in file_path_obj.parents:
                raise HTTPException(status_code=403, detail="不允許存取指定的檔案路徑。")
            if not file_path_obj.is_file():
                raise HTTPException(status_code=404, detail="在指定路徑上找不到檔案。")
            saved_file_path_str = str(file_path_obj)
            display_filename = file_path_obj.name
            task_model_size = req_data.model_size
            task_language = req_data.language
            task_beam_size = req_data.beam_size
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"無效的 JSON 請求: {e}")
    elif file and model_size is not None and beam_size is not None:
        transcribe_task_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix or ".wav"
        saved_file_path = UPLOADS_DIR / f"{transcribe_task_id}{file_extension}"
        display_filename = file.filename
        try:
            with open(saved_file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            saved_file_path_str = str(saved_file_path)
            task_model_size = model_size
            task_language = language
            task_beam_size = beam_size
        finally:
            await file.close()
    else:
        raise HTTPException(status_code=400, detail="請求格式不正確。")

    model_is_present = check_model_exists(task_model_size)
    final_transcribe_task_id = str(uuid.uuid4())
    transcription_payload = {"input_file": saved_file_path_str, "display_filename": display_filename, "output_dir": "transcripts", "model_size": task_model_size, "language": task_language, "beam_size": task_beam_size}

    tasks_to_return = []
    if not model_is_present:
        download_task_id = str(uuid.uuid4())
        db_client.add_task(download_task_id, json.dumps({"model_size": task_model_size}), task_type='download')
        db_client.add_task(final_transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe', depends_on=download_task_id)
        tasks_to_return.append({"task_id": download_task_id, "type": "download", "filename": f"模型: {task_model_size}"})
    else:
        db_client.add_task(final_transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe')

    tasks_to_return.append({"task_id": final_transcribe_task_id, "type": "transcribe", "filename": display_filename})
    return JSONResponse(content={"tasks": tasks_to_return})

@app.post("/api/youtube/set_api_key")
async def set_youtube_api_key(request: Request):
    global GEMINI_API_KEY
    payload = await request.json()
    api_key = payload.get("api_key")
    if not api_key: raise HTTPException(status_code=400, detail="請求中未包含 'api_key'。")

    tool_script = "tools/mock_gemini_processor.py" if IS_MOCK_MODE else "tools/gemini_processor.py"
    cmd = [sys.executable, tool_script, "--command=validate_key", "--api-key", api_key]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8')
    try: result_json = json.loads(proc.stdout)
    except json.JSONDecodeError: result_json = {"status": "error", "message": "金鑰驗證工具返回了無效的回應。"}

    if proc.returncode == 0 and result_json.get("status") == "success":
        GEMINI_API_KEY = api_key
        return JSONResponse(content={"status": "success", "message": "API 金鑰已成功驗證並儲存。"})
    else:
        raise HTTPException(status_code=400, detail=result_json.get("message", "金鑰無效或發生未知錯誤。"))

@app.get("/api/youtube/status")
async def get_youtube_status():
    if IS_MOCK_MODE: return {"enabled": True, "reason": "模擬模式已啟用。"}
    return {"enabled": True} if GEMINI_API_KEY else {"enabled": False, "reason": "尚未提供有效的 Google API 金鑰。請在下方輸入您的金鑰以啟用此功能。"}

@app.get("/api/youtube/models")
async def get_youtube_models():
    if IS_MOCK_MODE: return {"models": [{"id": "gemini-1.5-flash-mock", "name": "Gemini 1.5 Flash (模擬)"}]}
    if not GEMINI_API_KEY: raise HTTPException(status_code=401, detail="尚未設定 API 金鑰。")
    cmd = [sys.executable, "tools/gemini_processor.py", "--command=list_models", "--api-key", GEMINI_API_KEY]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
    return {"models": json.loads(result.stdout)}

@app.post("/api/youtube/process", status_code=202)
async def process_youtube_urls(request: Request):
    payload = await request.json()
    urls, model, download_only = payload.get("urls", []), payload.get("model"), payload.get("download_only", False)
    if not urls or (not download_only and not model): raise HTTPException(status_code=400, detail="請求參數不足。")
    tasks = []
    for url in filter(str.strip, urls):
        download_task_id = str(uuid.uuid4())
        db_client.add_task(download_task_id, json.dumps({"url": url, "output_dir": str(UPLOADS_DIR)}), task_type='youtube_download')
        task_info = {"url": url, "download_task_id": download_task_id}
        if download_only:
            task_info["type"] = "youtube_audio_only"
        else:
            process_task_id = str(uuid.uuid4())
            db_client.add_task(process_task_id, json.dumps({"model": model, "output_dir": "transcripts"}), task_type='gemini_process', depends_on=download_task_id)
            task_info.update({"type": "youtube_full_process", "process_task_id": process_task_id})
        tasks.append(task_info)
    return JSONResponse(content={"message": f"已為 {len(tasks)} 個 URL 建立處理任務。", "tasks": tasks})

def trigger_transcription(task_id: str, payload: dict, loop: asyncio.AbstractEventLoop):
    def _transcribe_in_thread():
        file_path, display_filename, model_size, lang, beam_size = payload.get("input_file"), payload.get("display_filename", Path(payload.get("input_file")).name), payload.get("model_size", "tiny"), payload.get("language"), payload.get("beam_size", 5)
        dummy_output_path = ROOT_DIR / "transcripts" / f"{task_id}.txt"
        cmd = [sys.executable, "tools/mock_transcriber.py" if IS_MOCK_MODE else "tools/transcriber.py", "--command=transcribe", f"--audio_file={file_path}", f"--output_file={dummy_output_path}", f"--model_size={model_size}", f"--beam_size={beam_size}"]
        if lang: cmd.append(f"--language={lang}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "TRANSCRIPTION_STATUS", "payload": {"task_id": task_id, "status": "starting", "filename": display_filename}}), loop)
        if proc.stdout:
            for line in iter(proc.stdout.readline, ''):
                try:
                    data = json.loads(line)
                    if data.get("type") == "segment": asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "TRANSCRIPTION_UPDATE", "payload": {"task_id": task_id, **data}}), loop)
                except json.JSONDecodeError: pass
        proc.wait()
        if proc.returncode == 0:
            result = {"transcript": dummy_output_path.read_text(encoding='utf-8').strip(), "transcript_path": str(dummy_output_path)}
            db_client.update_task_status(task_id, 'completed', json.dumps(result))
            final_message = {"type": "TRANSCRIPTION_STATUS", "payload": {"task_id": task_id, "status": "completed", "result": result}}
        else:
            final_message = {"type": "TRANSCRIPTION_STATUS", "payload": {"task_id": task_id, "status": "failed", "error": proc.stderr.read()}}
        asyncio.run_coroutine_threadsafe(manager.broadcast_json(final_message), loop)
    threading.Thread(target=_transcribe_in_thread).start()

def trigger_youtube_processing(task_id: str, task_type: str, loop: asyncio.AbstractEventLoop):
    # This function body remains largely the same as the previous version.
    # It correctly handles the two different task_types.
    global GEMINI_API_KEY
    def _process_in_thread():
        download_task_id = task_id
        dependent_task_id = None
        try:
            download_task_info = db_client.get_task_status(download_task_id)
            payload = json.loads(download_task_info['payload'])
            url = payload['url']

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_STATUS", "payload": {"task_id": download_task_id, "status": "downloading", "message": f"正在下載: {url}"}}), loop)

            tool_script_downloader = "tools/mock_youtube_downloader.py" if IS_MOCK_MODE else "tools/youtube_downloader.py"
            cmd_downloader = [sys.executable, tool_script_downloader, "--url", url, "--output-dir", str(UPLOADS_DIR)]
            process = subprocess.run(cmd_downloader, capture_output=True, text=True, check=True, encoding='utf-8')

            download_result = json.loads(process.stdout)
            db_client.update_task_status(download_task_id, 'completed', json.dumps(download_result))

            if task_type == "youtube_audio_only":
                asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_STATUS", "payload": {"task_id": download_task_id, "status": "completed", "result": download_result, "message": "僅下載音訊完成。"}}), loop)
                return

            if not IS_MOCK_MODE and not GEMINI_API_KEY: raise ValueError("YouTube AI 處理需要一個有效的 API 金鑰。")
            dependent_task_id = db_client.find_dependent_task(download_task_id)
            if not dependent_task_id: raise ValueError(f"找不到依賴於 {download_task_id} 的處理任務")
            process_task_info = db_client.get_task_status(dependent_task_id)
            process_payload = json.loads(process_task_info['payload'])
            model = process_payload['model']
            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_STATUS", "payload": {"task_id": dependent_task_id, "status": "processing", "message": f"使用 {model} 進行 AI 分析..."}}), loop)
            tool_script_processor = "tools/mock_gemini_processor.py" if IS_MOCK_MODE else "tools/gemini_processor.py"
            cmd_processor = [sys.executable, tool_script_processor, "--command=process", "--audio-file", download_result['output_path'], "--model", model, "--video-title", download_result.get('video_title', '無標題影片'), "--output-dir", str(ROOT_DIR / "transcripts")]
            if not IS_MOCK_MODE: cmd_processor.extend(["--api-key", GEMINI_API_KEY])
            result = subprocess.run(cmd_processor, capture_output=True, text=True, check=True, encoding='utf-8')
            process_result = json.loads(result.stdout)
            db_client.update_task_status(dependent_task_id, 'completed', json.dumps(process_result))
            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_STATUS", "payload": {"task_id": dependent_task_id, "status": "completed", "result": process_result}}), loop)
        except Exception as e:
            failed_task_id = dependent_task_id if dependent_task_id else download_task_id
            db_client.update_task_status(failed_task_id, 'failed', json.dumps({"error": str(e)}))
            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_STATUS", "payload": {"task_id": failed_task_id, "status": "failed", "error": str(e)}}), loop)
    threading.Thread(target=_process_in_thread).start()

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = json.loads(await websocket.receive_text())
            msg_type = message.get("type")
            payload = message.get("payload", {})
            loop = asyncio.get_running_loop()
            if msg_type == "START_TRANSCRIPTION":
                task_info = db_client.get_task_status(payload.get("task_id"))
                task_payload = json.loads(task_info['payload'])
                trigger_transcription(payload.get("task_id"), task_payload, loop)
            elif msg_type == "START_YOUTUBE_PROCESSING":
                trigger_youtube_processing(payload.get("task_id"), payload.get("task_type"), loop)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WebSocket 發生未預期錯誤: {e}", exc_info=True)
        if websocket in manager.active_connections: manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args, _ = parser.parse_known_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
