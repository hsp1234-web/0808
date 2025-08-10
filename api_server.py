# api_server.py
import argparse
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
import re
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Dict, List

# Import genai safely
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# 匯入新的資料庫客戶端
from db.client import get_client

os.environ['TZ'] = 'Asia/Taipei'
if sys.platform != 'win32':
    time.tzset()

# --- 模式與埠號設定 ---
cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("--mock", action="store_true", help="啟用模擬模式")
cli_parser.add_argument("--port", type=int, default=8001, help="指定伺服器監聽的埠號")
cli_args, _ = cli_parser.parse_known_args()
IS_MOCK_MODE = cli_args.mock
PORT = cli_args.port

ROOT_DIR = Path(__file__).resolve().parent

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
log = logging.getLogger('api_server')

def setup_database_logging():
    try:
        from db.log_handler import DatabaseLogHandler
        root_logger = logging.getLogger()
        if not any(isinstance(h, DatabaseLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(DatabaseLogHandler(source='api_server'))
            log.info("資料庫日誌處理器設定完成 (source: api_server)。")
    except Exception as e:
        log.error(f"整合資料庫日誌時發生錯誤: {e}", exc_info=True)

# --- WebSocket 連線管理器 ---
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

# --- Pydantic 模型 ---
class YouTubeProcessRequest(BaseModel):
    urls: List[str]
    model: str

app = FastAPI(title="鳳凰音訊轉錄儀 API (v3 - 重構)", version="3.0")
UPLOADS_DIR = ROOT_DIR / "uploads"
STATIC_DIR = ROOT_DIR / "static"
UPLOADS_DIR.mkdir(exist_ok=True)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- API Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_file_path = STATIC_DIR / "mp3.html"
    if not html_file_path.is_file():
        raise HTTPException(status_code=404, detail="找不到前端介面檔案 (mp3.html)")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)

@app.get("/api/key_status")
async def get_key_status():
    api_key = os.getenv("GOOGLE_API_KEY")
    return {"is_configured": bool(api_key)}

def get_model_version_score(api_name_lower):
    score = 9999
    if "latest" in api_name_lower: score = 0
    elif "preview" in api_name_lower: score = 1000
    return score

def sort_models_for_dropdown_key(model_api_name):
    name_lower = model_api_name.lower()
    if "gemini-1.5-flash" in name_lower: priority_group = 0
    elif "gemini-1.5-pro" in name_lower: priority_group = 1
    else: priority_group = 2
    return (priority_group, get_model_version_score(name_lower), name_lower)

@app.get("/api/models")
async def get_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse(content=[])
    if not genai:
         raise HTTPException(status_code=500, detail="google-generativeai 套件未安裝")
    try:
        genai.configure(api_key=api_key)
        models_from_api = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and ('flash' in m.name or 'pro' in m.name):
                 models_from_api.append({"display_name": m.display_name, "api_name": m.name})
        models_from_api.sort(key=lambda item: sort_models_for_dropdown_key(item['api_name']))
        return JSONResponse(content=models_from_api)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取模型列表失敗: {e}")

@app.post("/api/process_youtube", status_code=202)
async def process_youtube_url(request: YouTubeProcessRequest):
    tasks_created = []
    for url in request.urls:
        task_id = str(uuid.uuid4())
        payload = {"url": url, "model": request.model}
        db_client.add_task(task_id, json.dumps(payload), task_type='youtube_process')
        tasks_created.append({"task_id": task_id, "url": url, "model": request.model})
    return JSONResponse(content={"message": f"已為 {len(tasks_created)} 個 URL 成功建立任務。", "tasks": tasks_created}, status_code=202)

def trigger_youtube_processing(task_id: str, url: str, model: str, loop: asyncio.AbstractEventLoop):
    def _process_in_thread():
        log.info(f"🧵 [執行緒] 開始處理 YouTube 任務: {task_id}，URL: {url}")

        def log_stderr(pipe, pipe_name):
            """在單獨的執行緒中讀取並記錄子程序的 stderr。"""
            for line in iter(pipe.readline, ''):
                log.info(f"[{pipe_name} stderr] {line.strip()}")
            pipe.close()

        try:
            downloader_script = "tools/mock_youtube_downloader.py" if IS_MOCK_MODE else "tools/youtube_downloader.py"
            downloader_cmd = [sys.executable, downloader_script, f"--url={url}", f"--output-dir={str(UPLOADS_DIR)}"]
            process = subprocess.Popen(downloader_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

            # 啟動一個執行緒來非同步讀取下載器的 stderr
            stderr_thread = threading.Thread(target=log_stderr, args=(process.stderr, "Downloader"))
            stderr_thread.start()

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_PROCESS_STATUS", "payload": {"task_id": task_id, "status": "downloading", "detail": "Starting download..."}}), loop)

            downloaded_audio_path = None
            video_title = "Untitled"
            for line in iter(process.stdout.readline, ''):
                data = json.loads(line.strip())
                if data.get("type") == "progress":
                    asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_DOWNLOAD_PROGRESS", "payload": {"task_id": task_id, **data}}), loop)
                elif data.get("type") == "result":
                    if data.get("status") == "completed":
                        downloaded_audio_path = data.get("output_path")
                        video_title = data.get("video_title", video_title)
                    else:
                        # 等待 stderr 執行緒結束，以確保所有日誌都已擷取
                        process.wait()
                        stderr_thread.join()
                        raise RuntimeError(f"Downloader failed: {data.get('error', 'Unknown error')}")

            if not downloaded_audio_path:
                raise RuntimeError("Downloader did not provide output path.")

            processor_script = "tools/mock_gemini_processor.py" if IS_MOCK_MODE else "tools/gemini_processor.py"
            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_PROCESS_STATUS", "payload": {"task_id": task_id, "status": "processing", "detail": "AI is processing the audio..."}}), loop)

            processor_cmd = [sys.executable, processor_script, f"--audio-file={downloaded_audio_path}", f"--model={model}", f"--video-title={video_title}", f"--output-dir={str(UPLOADS_DIR)}"]
            proc_env = os.environ.copy()
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("API 金鑰未設定。")
            proc_env["GOOGLE_API_KEY"] = api_key

            proc_gemini = subprocess.Popen(processor_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=proc_env)

            # 啟動一個執行緒來非同步讀取 Gemini 處理器的 stderr
            gemini_stderr_thread = threading.Thread(target=log_stderr, args=(proc_gemini.stderr, "GeminiProcessor"))
            gemini_stderr_thread.start()

            html_report_path = None
            for line in iter(proc_gemini.stdout.readline, ''):
                data = json.loads(line.strip())
                if data.get("type") == "progress":
                    asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_PROCESS_STATUS", "payload": {"task_id": task_id, "status": "processing", "detail": data.get("detail")}}), loop)
                elif data.get("type") == "result" and data.get("status") == "completed":
                    html_report_path = data.get("html_report_path")

            if not html_report_path:
                raise RuntimeError("Gemini processor did not provide output path.")

            web_accessible_path = f"/uploads/{Path(html_report_path).name}"
            final_result_obj = {"downloaded_audio_path": str(downloaded_audio_path), "html_report_path": web_accessible_path, "video_title": video_title}
            db_client.update_task_status(task_id, 'completed', json.dumps(final_result_obj))

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({"type": "YOUTUBE_PROCESS_STATUS", "payload": {"task_id": task_id, "status": "completed", "result": final_result_obj}}), loop)
        except Exception as e:
            error_message = f"任務執行緒發生未預期錯誤: {e}"
            log.error(f"❌ [執行緒] YouTube 處理任務 '{task_id}' 失敗: {error_message}", exc_info=True)

            # 將錯誤資訊記錄到資料庫，這是讓系統返回 IDLE 狀態的關鍵
            error_payload = {"error": error_message}
            db_client.update_task_status(task_id, 'failed', json.dumps(error_payload))

            # 透過 WebSocket 通知前端失敗
            asyncio.run_coroutine_threadsafe(
                manager.broadcast_json({
                    "type": "YOUTUBE_PROCESS_STATUS",
                    "payload": {"task_id": task_id, "status": "failed", "error": error_message}
                }),
                loop
            )

    thread = threading.Thread(target=_process_in_thread)
    thread.start()

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")
            payload = message.get("payload", {})
            if msg_type == "START_YOUTUBE_PROCESSING":
                task_id = payload.get("task_id")
                task_info = db_client.get_task_status(task_id)
                if task_info:
                    task_payload = json.loads(task_info['payload'])
                    loop = asyncio.get_running_loop()
                    trigger_youtube_processing(task_id, task_payload.get("url"), task_payload.get("model"), loop)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WebSocket 發生未預期錯誤: {e}", exc_info=True)

# Other endpoints like /api/status/{task_id}, etc. are omitted for brevity but assumed to be here.

if __name__ == "__main__":
    import uvicorn
    setup_database_logging()
    log.info(f"🚀 啟動 API 伺服器 (v3)於埠號 {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
