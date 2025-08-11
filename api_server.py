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
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional, Dict, List

# 匯入新的資料庫客戶端
# from db import database # REMOVED: No longer used directly
from db.client import get_client

# --- JULES 於 2025-08-09 的修改：設定應用程式全域時區 ---
# 為了確保所有日誌和資料庫時間戳都使用一致的時區，我們在應用程式啟動的
# 最早期階段就將時區環境變數設定為 'Asia/Taipei'。
os.environ['TZ'] = 'Asia/Taipei'
if sys.platform != 'win32':
    time.tzset()
# --- 時區設定結束 ---

# --- 模式設定 ---
# JULES: 改為透過環境變數來決定模擬模式，以便與 Circus 整合
# 預設為非模擬模式 (真實模式)
IS_MOCK_MODE = os.environ.get("API_MODE", "real") == "mock"

# --- 路徑設定 ---
# 以此檔案為基準，定義專案根目錄
ROOT_DIR = Path(__file__).resolve().parent

# --- 主日誌設定 ---
# 主日誌器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # 輸出到控制台
)
log = logging.getLogger('api_server')

def setup_database_logging():
    """設定資料庫日誌處理器。"""
    try:
        from db.log_handler import DatabaseLogHandler
        root_logger = logging.getLogger()
        # 檢查是否已經有同類型的 handler，避免重複加入
        if not any(isinstance(h, DatabaseLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(DatabaseLogHandler(source='api_server'))
            log.info("資料庫日誌處理器設定完成 (source: api_server)。")
    except Exception as e:
        log.error(f"整合資料庫日誌時發生錯誤: {e}", exc_info=True)


# Frontend action logging is now handled by the centralized database logger.


# --- WebSocket 連線管理器 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info(f"新用戶端連線。目前共 {len(self.active_connections)} 個連線。")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        log.info(f"一個用戶端離線。目前共 {len(self.active_connections)} 個連線。")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def broadcast_json(self, data: dict):
        for connection in self.active_connections:
            await connection.send_json(data)

manager = ConnectionManager()


from contextlib import asynccontextmanager

# --- DB 客戶端 ---
# 在模組加載時獲取客戶端單例
# 客戶端內部有重試機制，會等待 DB 管理者服務就緒
db_client = get_client()

# --- FastAPI Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在應用程式啟動時執行的程式碼
    setup_database_logging()
    log.info("資料庫日誌處理器已透過 lifespan 事件設定。")
    yield
    # 可以在此處加入應用程式關閉時執行的程式碼

# --- FastAPI 應用實例 ---
app = FastAPI(title="鳳凰音訊轉錄儀 API (v3 - 重構)", version="3.0", lifespan=lifespan)

# --- 中介軟體 (Middleware) ---
# JULES: 新增 CORS 中介軟體以允許來自瀏覽器腳本的跨來源請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法
    allow_headers=["*"],  # 允許所有標頭
)

# --- 路徑設定 ---
# 以此檔案為基準，定義專案根目錄
ROOT_DIR = Path(__file__).resolve().parent
# 新的上傳檔案儲存目錄
UPLOADS_DIR = ROOT_DIR / "uploads"
# 靜態檔案目錄
STATIC_DIR = ROOT_DIR / "static"

# 確保目錄存在
UPLOADS_DIR.mkdir(exist_ok=True)
if not STATIC_DIR.exists():
    log.warning(f"靜態檔案目錄 {STATIC_DIR} 不存在，前端頁面可能無法載入。")
else:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- API 端點 ---

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """根端點，提供前端操作介面。"""
    html_file_path = STATIC_DIR / "mp3.html"
    if not html_file_path.is_file():
        log.error(f"找不到前端檔案: {html_file_path}")
        raise HTTPException(status_code=404, detail="找不到前端介面檔案 (mp3.html)")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)


def check_model_exists(model_size: str) -> bool:
    """
    檢查指定的 Whisper 模型是否已經被下載到本地快取。
    """
    # JULES'S FIX: 增加一個環境變數來強制使用模擬轉錄器，以支援混合模式測試
    force_mock = os.environ.get("FORCE_MOCK_TRANSCRIBER") == "true"
    tool_script = "tools/mock_transcriber.py" if IS_MOCK_MODE or force_mock else "tools/transcriber.py"
    log.info(f"使用 '{tool_script}' 檢查模型 '{model_size}' 是否存在...")

    # 我們透過呼叫一個輕量級的工具腳本來檢查。
    check_command = [sys.executable, tool_script, "--command=check", f"--model_size={model_size}"]
    try:
        # 在模擬模式下，mock_transcriber.py 會永遠回傳 "exists"
        result = subprocess.run(check_command, capture_output=True, text=True, check=True)
        output = result.stdout.strip().lower()
        log.info(f"模型 '{model_size}' 檢查結果: {output}")
        # 必須完全匹配 "exists"，避免 "not_exists" 被錯誤判斷為 True
        return output == "exists"
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.error(f"檢查模型 '{model_size}' 時發生錯誤: {e}")
        return False

@app.post("/api/transcribe", status_code=202)
async def create_transcription_task(
    file: UploadFile = File(...),
    model_size: str = Form("tiny"),
    language: Optional[str] = Form(None),
    beam_size: int = Form(5)
):
    """
    接收音訊檔案，根據模型是否存在，決定是直接建立轉錄任務，
    還是先建立一個下載任務和一個依賴於它的轉錄任務。
    """
    # 1. 檢查模型是否存在
    model_is_present = check_model_exists(model_size)

    # 2. 保存上傳的檔案
    transcribe_task_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix or ".wav"
    saved_file_path = UPLOADS_DIR / f"{transcribe_task_id}{file_extension}"
    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log.info(f"檔案已儲存至: {saved_file_path}")
    except Exception as e:
        log.error(f"❌ 儲存檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"無法儲存上傳的檔案: {e}")
    finally:
        await file.close()

    # 3. 根據模型是否存在來建立任務
    transcription_payload = {
        "input_file": str(saved_file_path),
        "original_filename": file.filename, # JULES'S FIX: Store the original filename
        "output_dir": "transcripts",
        "model_size": model_size,
        "language": language,
        "beam_size": beam_size
    }

    if model_is_present:
        # 模型已存在，直接建立轉錄任務
        log.info(f"✅ 模型 '{model_size}' 已存在，直接建立轉錄任務: {transcribe_task_id}")
        db_client.add_task(transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe')
        # JULES: 修正 API 回應，使其與前端的通用處理邏輯一致，補上 type 欄位
        return {"task_id": transcribe_task_id, "type": "transcribe"}
    else:
        # 模型不存在，建立下載任務和依賴的轉錄任務
        download_task_id = str(uuid.uuid4())
        log.warning(f"⚠️ 模型 '{model_size}' 不存在。建立下載任務 '{download_task_id}' 和依賴的轉錄任務 '{transcribe_task_id}'")

        download_payload = {"model_size": model_size}
        db_client.add_task(download_task_id, json.dumps(download_payload), task_type='download')

        db_client.add_task(transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe', depends_on=download_task_id)

        # 我們回傳轉錄任務的 ID，讓前端可以追蹤最終結果
        return JSONResponse(content={"tasks": [
            {"task_id": download_task_id, "type": "download"},
            {"task_id": transcribe_task_id, "type": "transcribe"}
        ]})


@app.get("/api/status/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """
    根據任務 ID，從資料庫查詢任務狀態。
    """
    log.debug(f"🔍 正在查詢任務狀態: {task_id}")
    status_info = db_client.get_task_status(task_id)

    if not status_info:
        log.warning(f"❓ 找不到任務 ID: {task_id}")
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID")

    # DBClient 回傳的已經是 dict，無需轉換
    response_data = status_info

    # 嘗試解析 JSON 結果
    if response_data.get("result"):
        try:
            response_data["result"] = json.loads(response_data["result"])
        except json.JSONDecodeError:
            # 如果不是合法的 JSON，就以原始字串形式回傳
            log.warning(f"任務 {task_id} 的結果不是有效的 JSON 格式。")
            pass

    log.info(f"✅ 回傳任務 {task_id} 的狀態: {response_data['status']}")
    return JSONResponse(content=response_data)


@app.post("/api/log/action", status_code=200)
async def log_action_endpoint(payload: Dict):
    """
    接收前端發送的操作日誌，並透過資料庫日誌處理器記錄。
    """
    action = payload.get("action", "unknown_action")
    # 獲取一個專門的 logger 來標識這些日誌的來源為 'frontend_action'
    # DatabaseLogHandler 會擷取這個日誌，並將其與 logger 名稱一起存入資料庫
    action_logger = logging.getLogger('frontend_action')
    action_logger.info(action)

    log.info(f"📝 已將前端操作記錄到資料庫: {action}") # 同時在主控台也顯示日誌
    return {"status": "logged"}


import psutil

@app.get("/api/application_status")
async def get_application_status():
    """
    獲取核心應用的狀態，例如模型是否已載入。
    """
    # TODO: 這部分將在後續與 worker 狀態同步
    return {
        "model_loaded": False,
        "active_model": None,
        "message": "等待使用者操作"
    }

@app.get("/api/system_stats")
async def get_system_stats():
    """
    獲取並回傳當前的系統資源使用狀態（CPU, RAM, GPU）。
    """
    # CPU
    cpu_usage = psutil.cpu_percent(interval=0.1)

    # RAM
    ram = psutil.virtual_memory()
    ram_usage = ram.percent

    # GPU (透過 nvidia-smi)
    gpu_usage = None
    gpu_detected = False
    try:
        # 執行 nvidia-smi 命令
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, check=True
        )
        # 解析輸出
        gpu_usage = float(result.stdout.strip())
        gpu_detected = True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        # nvidia-smi 不存在或執行失敗
        log.debug(f"無法獲取 GPU 資訊: {e}")
        gpu_usage = None
        gpu_detected = False

    return {
        "cpu_usage": cpu_usage,
        "ram_usage": ram_usage,
        "gpu_usage": gpu_usage,
        "gpu_detected": gpu_detected,
    }


@app.get("/api/tasks")
async def get_all_tasks_endpoint():
    """
    獲取所有任務的列表，用於前端展示。
    """
    tasks = db_client.get_all_tasks()
    # 嘗試解析 payload 和 result 中的 JSON 字串
    for task in tasks:
        try:
            if task.get("payload"):
                task["payload"] = json.loads(task["payload"])
        except (json.JSONDecodeError, TypeError):
            log.warning(f"任務 {task.get('task_id')} 的 payload 不是有效的 JSON。")
            pass # 保持原樣
        try:
            if task.get("result"):
                task["result"] = json.loads(task["result"])
        except (json.JSONDecodeError, TypeError):
            log.warning(f"任務 {task.get('task_id')} 的 result 不是有效的 JSON。")
            pass # 保持原樣
    return JSONResponse(content=tasks)


@app.get("/api/logs")
async def get_system_logs_endpoint(
    levels: List[str] = Query(None, alias="level"),
    sources: List[str] = Query(None, alias="source")
):
    """
    獲取系統日誌，可按等級和來源進行篩選。
    """
    log.info(f"API: 正在查詢系統日誌 (Levels: {levels}, Sources: {sources})")
    try:
        logs = db_client.get_system_logs(levels=levels, sources=sources)
        return JSONResponse(content=logs)
    except Exception as e:
        log.error(f"❌ 查詢系統日誌時 API 出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查詢系統日誌時發生內部錯誤")


@app.get("/api/download/{task_id}")
async def download_transcript(task_id: str):
    """
    根據任務 ID 下載轉錄結果檔案。
    """
    task = db_client.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID。")

    if task['status'] != 'completed':
        raise HTTPException(status_code=400, detail="任務尚未完成，無法下載。")

    try:
        # 從 result 欄位解析出檔名
        result_data = json.loads(task['result'])
        # 依序檢查可能的路徑鍵名，以支援所有任務類型
        output_filename = (
            result_data.get("transcript_path") or
            result_data.get("output_path") or
            result_data.get("html_report_path") or
            result_data.get("pdf_report_path")
        )

        if not output_filename:
            raise HTTPException(status_code=500, detail="任務結果中未包含有效的檔案路徑。")

        file_path = Path(output_filename)
        if not file_path.is_file():
            log.error(f"❌ 轉錄檔案不存在: {file_path}")
            raise HTTPException(status_code=404, detail="轉錄檔案遺失或無法讀取。")

        # 提供檔案下載
        from fastapi.responses import FileResponse
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            media_type = 'application/pdf'
        elif ext == '.html':
            media_type = 'text/html'
        else:
            media_type = 'text/plain'
        return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)

    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"❌ 解析任務 {task_id} 的結果時出錯: {e}")
        raise HTTPException(status_code=500, detail="無法解析任務結果。")


# --- YouTube 功能相關 API ---

@app.post("/api/youtube/validate_api_key")
async def validate_api_key(request: Request):
    """接收前端傳來的 API Key 並進行驗證。"""
    try:
        payload = await request.json()
        api_key = payload.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="未提供 API 金鑰。")

        # 在模擬模式下，只要金鑰非空就視為有效
        if IS_MOCK_MODE:
            log.info("模擬模式：將非空 API 金鑰視為有效。")
            return {"valid": True}

        # 真實模式下，呼叫工具進行驗證
        tool_script = "tools/gemini_processor.py"
        cmd = [sys.executable, tool_script, "--command=validate_key"]

        # 將金鑰作為環境變數傳遞給子程序，更安全
        env = os.environ.copy()
        env["GOOGLE_API_KEY"] = api_key

        # 設定 check=False，因為我們預期在金鑰無效時程序會失敗
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env, check=False)

        if result.returncode == 0:
            log.info(f"API 金鑰驗證成功。")
            return {"valid": True}
        else:
            log.warning(f"API 金鑰驗證失敗。Stderr: {result.stderr.strip()}")
            # 嘗試從 stderr 中提取更具體的錯誤訊息
            error_message = result.stderr.strip()
            if "API key not valid" in error_message:
                detail = "API 金鑰無效。請檢查您的金鑰是否正確。"
            else:
                detail = "金鑰驗證失敗，可能是網路問題或金鑰權限不足。"
            return JSONResponse(status_code=400, content={"valid": False, "detail": detail})

    except Exception as e:
        log.error(f"驗證 API 金鑰時發生伺服器內部錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤: {e}")


@app.get("/api/youtube/models")
async def get_youtube_models():
    """獲取可用的 Gemini 模型列表。"""
    # 在模擬模式下，回傳一個固定的假列表
    if IS_MOCK_MODE:
        return {
            "models": [
                {"id": "gemini-pro-mock", "name": "Gemini Pro (模擬)"},
                {"id": "gemini-1.5-flash-mock", "name": "Gemini 1.5 Flash (模擬)"}
            ]
        }

    # 真實模式下，從 gemini_processor.py 獲取
    # 注意：此端點現在依賴於一個有效的 GOOGLE_API_KEY 環境變數
    try:
        if not os.environ.get("GOOGLE_API_KEY"):
             raise HTTPException(status_code=401, detail="後端尚未設定有效的 Google API 金鑰。")

        tool_script = "tools/gemini_processor.py"
        cmd = [sys.executable, tool_script, "--command=list_models"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        models = json.loads(result.stdout)
        return {"models": models}
    except subprocess.CalledProcessError as e:
        log.error(f"獲取 Gemini 模型列表失敗，可能是因為 API 金鑰無效。Stderr: {e.stderr}")
        raise HTTPException(status_code=401, detail="無法使用提供的 API 金鑰獲取模型列表。")
    except Exception as e:
        log.error(f"獲取 Gemini 模型列表時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="無法獲取 Gemini 模型列表。")


@app.post("/api/youtube/process", status_code=202)
async def process_youtube_urls(request: Request):
    """
    接收 YouTube URL，根據 'download_only' 旗標決定是僅下載音訊，還是執行完整的 AI 分析流程。
    """
    payload = await request.json()
    # JULES'S FIX: 前端發送的是 'requests' 物件陣列，而非 'urls' 字串陣列。修正這裡以正確解析。
    requests_list = payload.get("requests", [])
    model = payload.get("model")
    download_only = payload.get("download_only", False)

    if not requests_list:
        raise HTTPException(status_code=400, detail="請求中必須包含 'requests'。")
    if not download_only and not model:
        raise HTTPException(status_code=400, detail="執行完整分析時必須提供 'model'。")

    tasks = []
    for req_item in requests_list:
        url = req_item.get("url")
        filename = req_item.get("filename") # 雖然目前未使用，但先讀取出來

        if not url or not url.strip():
            continue

        task_id = str(uuid.uuid4())

        if download_only:
            # 僅下載模式：只建立一個下載任務
            # 將自訂檔名存入 payload，以便未來使用
            task_payload = {"url": url, "output_dir": str(UPLOADS_DIR), "custom_filename": filename}
            db_client.add_task(task_id, json.dumps(task_payload), task_type='youtube_download_only')
            tasks.append({"url": url, "task_id": task_id})
        else:
            # 完整分析模式：建立下載和處理兩個任務
            download_task_id = task_id
            process_task_id = str(uuid.uuid4())

            download_payload = {"url": url, "output_dir": str(UPLOADS_DIR), "custom_filename": filename}
            process_payload = {"model": model, "output_dir": "transcripts"}

            db_client.add_task(download_task_id, json.dumps(download_payload), task_type='youtube_download')
            db_client.add_task(process_task_id, json.dumps(process_payload), task_type='gemini_process', depends_on=download_task_id)

            tasks.append({"url": url, "task_id": download_task_id})

    return JSONResponse(content={"message": f"已為 {len(tasks)} 個 URL 建立處理任務。", "tasks": tasks})


def trigger_model_download(model_size: str, loop: asyncio.AbstractEventLoop):
    """
    在一個單獨的執行緒中執行模型下載，並透過 WebSocket 回報結果。
    這個版本會逐行讀取 stdout 來獲取即時的 JSON 進度更新。
    """
    def _download_in_thread():
        log.info(f"🧵 [執行緒] 開始下載模型: {model_size}")
        try:
            tool_script = "tools/mock_transcriber.py" if IS_MOCK_MODE else "tools/transcriber.py"
            cmd = [sys.executable, tool_script, "--command=download", f"--model_size={model_size}"]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1 # Line-buffered
            )

            # 逐行讀取 stdout 以獲取進度更新
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # 建立 WebSocket 訊息
                        message = {
                            "type": "DOWNLOAD_STATUS",
                            "payload": {
                                "model": model_size,
                                "status": "downloading",
                                **data  # 這會包含 'type', 'percent', 'description' 等
                            }
                        }
                        asyncio.run_coroutine_threadsafe(manager.broadcast_json(message), loop)
                    except json.JSONDecodeError:
                        log.warning(f"[執行緒] 無法解析來自 transcriber 的下載進度 JSON: {line}")

            process.wait() # 等待程序結束

            # 根據程序的返回碼決定最終狀態
            if process.returncode == 0:
                log.info(f"✅ [執行緒] 模型 '{model_size}' 下載成功。")
                message = {
                    "type": "DOWNLOAD_STATUS",
                    "payload": {"model": model_size, "status": "completed", "progress": 100}
                }
            else:
                stderr_output = process.stderr.read() if process.stderr else "N/A"
                log.error(f"❌ [執行緒] 模型 '{model_size}' 下載失敗。 Stderr: {stderr_output}")
                message = {
                    "type": "DOWNLOAD_STATUS",
                    "payload": {"model": model_size, "status": "failed", "error": stderr_output}
                }

            asyncio.run_coroutine_threadsafe(manager.broadcast_json(message), loop)

        except Exception as e:
            log.error(f"❌ [執行緒] 下載執行緒中發生嚴重錯誤: {e}", exc_info=True)
            message = {
                "type": "DOWNLOAD_STATUS",
                "payload": {"model": model_size, "status": "failed", "error": str(e)}
            }
            asyncio.run_coroutine_threadsafe(manager.broadcast_json(message), loop)

    # 建立並啟動執行緒
    thread = threading.Thread(target=_download_in_thread)
    thread.start()


def trigger_transcription(task_id: str, file_path: str, model_size: str, language: Optional[str], beam_size: int, loop: asyncio.AbstractEventLoop, original_filename: Optional[str] = None):
    """
    在一個單獨的執行緒中執行轉錄，並透過 WebSocket 即時串流結果。
    """
    def _transcribe_in_thread():
        display_name = original_filename or file_path
        log.info(f"🧵 [執行緒] 開始處理轉錄任務: {task_id}，檔案: {display_name}")

        # 準備一個假的輸出檔案路徑，因為 transcriber.py 需要它，但我們實際上是從 stdout 讀取
        output_dir = ROOT_DIR / "transcripts"
        output_dir.mkdir(exist_ok=True)
        dummy_output_path = output_dir / f"{task_id}.txt"

        try:
            # JULES'S FIX: 增加一個環境變數來強制使用模擬轉錄器，以支援混合模式測試
            force_mock = os.environ.get("FORCE_MOCK_TRANSCRIBER") == "true"
            tool_script = "tools/mock_transcriber.py" if IS_MOCK_MODE or force_mock else "tools/transcriber.py"
            cmd = [
                sys.executable,
                tool_script,
                "--command=transcribe",
                f"--audio_file={file_path}",
                f"--output_file={dummy_output_path}",
                f"--model_size={model_size}",
            ]
            if language:
                cmd.append(f"--language={language}")
            # 新增 beam_size 參數
            cmd.append(f"--beam_size={beam_size}")

            log.info(f"執行轉錄指令: {' '.join(map(str, cmd))}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1 # Line-buffered
            )

            # JULES'S FIX: Use the original filename for the UI if available.
            start_message_filename = original_filename or Path(file_path).name
            start_message = {
                "type": "TRANSCRIPTION_STATUS",
                "payload": {"task_id": task_id, "status": "starting", "filename": start_message_filename}
            }
            asyncio.run_coroutine_threadsafe(manager.broadcast_json(start_message), loop)

            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        # JULES' FIX: 只轉發 'segment' 類型的訊息以避免非預期的 UI 元素
                        if data.get("type") == "segment":
                            message = {
                                "type": "TRANSCRIPTION_UPDATE",
                                "payload": {"task_id": task_id, **data}
                            }
                            asyncio.run_coroutine_threadsafe(manager.broadcast_json(message), loop)
                    except json.JSONDecodeError:
                        log.warning(f"[執行緒] 無法解析來自 transcriber 的 JSON 行: {line}")

            process.wait()

            if process.returncode == 0:
                log.info(f"✅ [執行緒] 轉錄任務 '{task_id}' 成功完成。")

                # 讀取結果並更新資料庫狀態
                final_transcript = dummy_output_path.read_text(encoding='utf-8').strip()
                final_result_obj = {
                    "transcript": final_transcript,
                    "transcript_path": str(dummy_output_path)
                }
                db_client.update_task_status(task_id, 'completed', json.dumps(final_result_obj))
                log.info(f"✅ [執行緒] 已將任務 {task_id} 的狀態和結果更新至資料庫。")

                final_message = {
                    "type": "TRANSCRIPTION_STATUS",
                    "payload": {"task_id": task_id, "status": "completed", "result": final_result_obj}
                }
            else:
                stderr_output = process.stderr.read() if process.stderr else "N/A"
                log.error(f"❌ [執行緒] 轉錄任務 '{task_id}' 失敗。返回碼: {process.returncode}。Stderr: {stderr_output}")
                final_message = {
                    "type": "TRANSCRIPTION_STATUS",
                    "payload": {"task_id": task_id, "status": "failed", "error": stderr_output}
                }

            asyncio.run_coroutine_threadsafe(manager.broadcast_json(final_message), loop)

        except Exception as e:
            log.error(f"❌ [執行緒] 轉錄執行緒中發生嚴重錯誤: {e}", exc_info=True)
            error_message = {
                "type": "TRANSCRIPTION_STATUS",
                "payload": {"task_id": task_id, "status": "failed", "error": str(e)}
            }
            asyncio.run_coroutine_threadsafe(manager.broadcast_json(error_message), loop)

    thread = threading.Thread(target=_transcribe_in_thread)
    thread.start()


def trigger_youtube_processing(task_id: str, loop: asyncio.AbstractEventLoop):
    """在一個單獨的執行緒中執行 YouTube 處理流程。"""
    def _process_in_thread():
        log.info(f"🧵 [執行緒] 開始處理 YouTube 任務，ID: {task_id}")

        task_info = db_client.get_task_status(task_id)
        if not task_info:
            log.error(f"❌ [執行緒] 找不到任務 {task_id}")
            return

        task_type = task_info.get('type')

        try:
            # --- 步驟 1: 下載音訊 (所有 YouTube 任務都需要) ---
            payload = json.loads(task_info['payload'])
            url = payload['url']

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({
                "type": "YOUTUBE_STATUS",
                "payload": {"task_id": task_id, "status": "downloading", "message": f"正在下載: {url}", "task_type": task_type}
            }), loop)

            tool_script = "tools/mock_youtube_downloader.py" if IS_MOCK_MODE else "tools/youtube_downloader.py"
            cmd = [sys.executable, tool_script, "--url", url, "--output-dir", str(UPLOADS_DIR)]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

            last_line = ""
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if line: last_line = line

            process.wait()
            if process.returncode != 0:
                stderr_output = process.stderr.read() if process.stderr else "N/A"
                raise RuntimeError(f"YouTube downloader failed: {stderr_output}")

            download_result = json.loads(last_line)
            audio_file_path = download_result['output_path']
            video_title = download_result.get('video_title', '無標題影片')
            log.info(f"✅ [執行緒] YouTube 音訊下載完成: {audio_file_path}")

            # --- 步驟 2: 根據任務類型決定下一步 ---
            if task_type == 'youtube_download_only':
                # 如果只是下載任務，到此結束
                db_client.update_task_status(task_id, 'completed', json.dumps(download_result))
                log.info(f"✅ [執行緒] '僅下載音訊' 任務 {task_id} 完成。")

                asyncio.run_coroutine_threadsafe(manager.broadcast_json({
                    "type": "YOUTUBE_STATUS",
                    "payload": {"task_id": task_id, "status": "completed", "result": download_result, "task_type": "download_only"}
                }), loop)
                return # 結束執行緒

            # --- 步驟 3: 執行 Gemini AI 分析 (僅適用於完整流程) ---
            db_client.update_task_status(task_id, 'completed', json.dumps(download_result))

            dependent_task_id = db_client.find_dependent_task(task_id)
            if not dependent_task_id:
                raise ValueError(f"找不到依賴於 {task_id} 的 gemini_process 任務")

            process_task_info = db_client.get_task_status(dependent_task_id)
            process_payload = json.loads(process_task_info['payload'])
            model = process_payload['model']

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({
                "type": "YOUTUBE_STATUS",
                "payload": {"task_id": dependent_task_id, "status": "processing", "message": f"使用 {model} 進行 AI 分析...", "task_type": "gemini_process"}
            }), loop)

            tool_script = "tools/mock_gemini_processor.py" if IS_MOCK_MODE else "tools/gemini_processor.py"
            report_output_dir = ROOT_DIR / "transcripts"
            report_output_dir.mkdir(exist_ok=True)

            cmd = [
                sys.executable, tool_script,
                "--audio-file", audio_file_path,
                "--model", model,
                "--output-dir", str(report_output_dir),
                "--video-title", video_title
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
            process_result = json.loads(result.stdout)

            db_client.update_task_status(dependent_task_id, 'completed', json.dumps(process_result))
            log.info(f"✅ [執行緒] Gemini AI 處理完成。")

            asyncio.run_coroutine_threadsafe(manager.broadcast_json({
                "type": "YOUTUBE_STATUS",
                "payload": {"task_id": dependent_task_id, "status": "completed", "result": process_result, "task_type": "gemini_process"}
            }), loop)

        except Exception as e:
            log.error(f"❌ [執行緒] YouTube 處理鏈中發生錯誤: {e}", exc_info=True)
            # 確定要更新哪個任務為失敗狀態
            failed_task_id = 'dependent_task_id' if 'dependent_task_id' in locals() and dependent_task_id else task_id
            db_client.update_task_status(failed_task_id, 'failed', json.dumps({"error": str(e)}))
            asyncio.run_coroutine_threadsafe(manager.broadcast_json({
                "type": "YOUTUBE_STATUS",
                "payload": {"task_id": failed_task_id, "status": "failed", "error": str(e)}
            }), loop)

    thread = threading.Thread(target=_process_in_thread)
    thread.start()


@app.get("/api/debug/latest_frontend_action_log")
async def get_latest_frontend_action_log():
    """
    [僅供測試] 獲取最新的前端操作日誌。
    用於 E2E 測試，以驗證日誌是否已成功寫入資料庫。
    """
    try:
        # 我們只關心來自 'frontend_action' logger 的日誌
        logs = db_client.get_system_logs(sources=['frontend_action'])
        if not logs:
            # 如果沒有日誌，返回一個清晰的空回應，而不是 404
            return JSONResponse(content={"latest_log": None}, status_code=200)

        # get_system_logs 按時間戳升序排序，所以最後一個就是最新的
        latest_log = logs[-1]
        return JSONResponse(content={"latest_log": latest_log})
    except Exception as e:
        log.error(f"❌ 查詢最新前端日誌時出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查詢最新前端日誌時發生內部錯誤")


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            log.info(f"從 WebSocket 收到訊息: {data}")

            try:
                message = json.loads(data)
                msg_type = message.get("type")
                payload = message.get("payload", {})

                if msg_type == "DOWNLOAD_MODEL":
                    model_size = payload.get("model")
                    if model_size:
                        log.info(f"收到下載 '{model_size}' 模型的請求。")
                        await manager.broadcast_json({
                            "type": "DOWNLOAD_STATUS",
                            "payload": {"model": model_size, "status": "starting", "progress": 0}
                        })
                        loop = asyncio.get_running_loop()
                        trigger_model_download(model_size, loop)
                    else:
                        await manager.broadcast_json({"type": "ERROR", "payload": "缺少模型大小參數"})

                elif msg_type == "START_TRANSCRIPTION":
                    task_id = payload.get("task_id")
                    if not task_id:
                        await manager.broadcast_json({"type": "ERROR", "payload": "缺少 task_id 參數"})
                        continue

                    task_info = db_client.get_task_status(task_id)
                    if not task_info:
                        await manager.broadcast_json({"type": "ERROR", "payload": f"找不到任務 {task_id}"})
                        continue

                    try:
                        task_payload = json.loads(task_info['payload'])
                        file_path = task_payload.get("input_file")
                        model_size = task_payload.get("model_size", "tiny")
                        language = task_payload.get("language")
                        beam_size = task_payload.get("beam_size", 5)
                        original_filename = task_payload.get("original_filename") # JULES'S FIX
                    except (json.JSONDecodeError, KeyError) as e:
                        await manager.broadcast_json({"type": "ERROR", "payload": f"解析任務 {task_id} 的 payload 失敗: {e}"})
                        continue

                    if not file_path:
                        await manager.broadcast_json({"type": "ERROR", "payload": "任務 payload 中缺少檔案路徑"})
                    else:
                        display_name = original_filename or file_path
                        log.info(f"收到開始轉錄 '{display_name}' 的請求 (來自任務 {task_id})。")
                        loop = asyncio.get_running_loop()
                        trigger_transcription(task_id, file_path, model_size, language, beam_size, loop, original_filename=original_filename)

                elif msg_type == "START_YOUTUBE_PROCESSING":
                    task_id = payload.get("task_id") # This is the download_task_id
                    if not task_id:
                        await manager.broadcast_json({"type": "ERROR", "payload": "缺少 task_id 參數"})
                        continue

                    log.info(f"收到開始處理 YouTube 任務鏈的請求 (起始任務 ID: {task_id})。")
                    loop = asyncio.get_running_loop()
                    trigger_youtube_processing(task_id, loop)

                else:
                    await manager.broadcast_json({
                        "type": "ECHO",
                        "payload": f"已收到未知類型的訊息: {msg_type}"
                    })

            except json.JSONDecodeError:
                log.error("收到了非 JSON 格式的 WebSocket 訊息。")
                await manager.broadcast_json({"type": "ERROR", "payload": "訊息必須是 JSON 格式"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("WebSocket 用戶端已離線。")
    except Exception as e:
        log.error(f"WebSocket 發生未預期錯誤: {e}", exc_info=True)
        # 確保在發生錯誤時也中斷連線
        if websocket in manager.active_connections:
            manager.disconnect(websocket)


@app.get("/api/health")
async def health_check():
    """提供一個簡單的健康檢查端點。"""
    return {"status": "ok", "message": "API Server is running."}


@app.post("/api/internal/notify_task_update", status_code=200)
async def notify_task_update(payload: Dict):
    """
    一個內部端點，供 Worker 程序在任務完成時呼叫，
    以便透過 WebSocket 將更新廣播給前端。
    """
    task_id = payload.get("task_id")
    status = payload.get("status")
    result = payload.get("result")
    log.info(f"🔔 收到來自 Worker 的任務更新通知: Task {task_id} -> {status}")

    # 確保 result 是字典格式
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            log.warning(f"來自 worker 的任務 {task_id} 結果不是有效的 JSON 格式。")

    message = {
        "type": "TRANSCRIPTION_STATUS",
        "payload": {
            "task_id": task_id,
            "status": status,
            "result": result
        }
    }
    await manager.broadcast_json(message)
    return {"status": "notification_sent"}


# --- 主程式啟動 ---
if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="鳳凰音訊轉錄儀 API 伺服器")
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="伺服器監聽的埠號"
    )
    args, _ = parser.parse_known_args()

    # JULES: 移除此處的資料庫初始化呼叫。
    # 父程序 orchestrator.py 將會負責此事，以避免競爭條件。

    # JULES'S FIX: The database logging is now set up via the app's lifespan event.
    # setup_database_logging() is no longer needed here.

    log.info("🚀 啟動 API 伺服器 (v3)...")
    log.info(f"請在瀏覽器中開啟 http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
