# api_server.py
import uuid
import shutil
import logging
import json
import subprocess
import sys
import os
import time
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import asynccontextmanager
from urllib.parse import unquote, quote
from pydantic import BaseModel, ValidationError
import psutil

# --- 修正模組匯入路徑 ---
# 將專案的 src 目錄新增到 Python 的搜尋路徑中，
# 這樣才能正確找到 db.client 等模組。
SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from db.client import get_client
from shared import constants
import inspect

# --- JULES 於 2025-08-09 的修改：設定應用程式全域時區 ---
# 為了確保所有日誌和資料庫時間戳都使用一致的時區，我們在應用程式啟動的
# 最早期階段就將時區環境變數設定為 'Asia/Taipei'。
os.environ['TZ'] = 'Asia/Taipei'
if sys.platform != 'win32':
    time.tzset()
# --- 時區設定結束 ---


# --- 路徑設定 ---
# 以此檔案為基準，定義專案根目錄
# 因為此檔案現在位於 src/api/ 中，所以根目錄是其上上層目錄
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

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
        # 層級三：後端資料驗證
        try:
            # 在廣播前，使用 Pydantic 模型驗證資料結構
            validated_message = WebSocketMessage(**data)
            message_to_send = validated_message.model_dump_json()
            for connection in self.active_connections:
                await connection.send_text(message_to_send)
        except ValidationError as e:
            # 如果資料格式不符，則在後端記錄嚴重錯誤，而不是發送格式錯誤的資料
            log.error(f"準備廣播的 WebSocket 訊息格式無效: {e}\n原始資料: {data}")


manager = ConnectionManager()

# --- Pydantic 模型定義 (資料契約) ---

class TaskPayload(BaseModel):
    # 這個模型可以根據需要變得更具體，但目前允許任意欄位
    class Config:
        extra = 'allow'

class WebSocketMessage(BaseModel):
    type: str
    payload: dict # 為了保持彈性，暫時設為 dict


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
# 新的上傳檔案儲存目錄
UPLOADS_DIR = ROOT_DIR / "uploads"
# 靜態檔案目錄
STATIC_DIR = ROOT_DIR / "src" / "static"

# 確保目錄存在
UPLOADS_DIR.mkdir(exist_ok=True)
if not STATIC_DIR.exists():
    log.warning(f"靜態檔案目錄 {STATIC_DIR} 不存在，前端頁面可能無法載入。")
else:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    # JULES'S FIX (2025-08-13): 移除有問題的 StaticFiles 掛載，改用自訂端點

# JULES'S FIX (2025-08-13): 根據計畫，新增此端點來處理複雜檔名
@app.get("/media/{file_path:path}")
async def serve_media_files(file_path: str):
    """
    一個新的API端點，專門用來安全地提供媒體檔案。
    它會手動處理URL解碼，以解決複雜檔名的問題。
    """
    try:
        # URL 解碼，將 %20 轉為空格，處理中文等
        decoded_path = unquote(file_path)
        # 建立一個安全的路徑，避免路徑遍歷攻擊
        safe_path = os.path.normpath(os.path.join(UPLOADS_DIR, decoded_path))

        # 再次確認路徑是在 UPLOADS_DIR 下
        if not safe_path.startswith(str(UPLOADS_DIR)):
             raise HTTPException(status_code=403, detail="禁止存取。")

        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            return FileResponse(safe_path)
        else:
            log.warning(f"請求的媒體檔案不存在: {safe_path}")
            return JSONResponse(status_code=404, content={"detail": "File not found"})
    except Exception as e:
        log.error(f"服務媒體檔案時發生錯誤: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(e)})


def convert_to_media_url(absolute_path_str: str) -> str:
    """將絕對檔案系統路徑轉換為可公開存取的 /media URL。"""
    try:
        absolute_path = Path(absolute_path_str)
        # 尋找相對於 UPLOADS_DIR 的路徑
        relative_path = absolute_path.relative_to(UPLOADS_DIR)
        # 將路徑的每個部分都進行 URL 編碼，以處理特殊字元
        # safe='' 參數確保連 '/' 也會被編碼，如果有的話
        encoded_path = '/'.join(quote(part, safe='') for part in relative_path.parts)

        # JULES DEBUG (2025-08-31): 根據最新分析報告，此處是造成媒體預覽失敗的關鍵。
        # 舊的寫法 `relative_path.as_posix()` 沒有對檔名中的 '#' 或空格等特殊字元進行編碼，
        # 導致瀏覽器無法正確請求 URL。新的寫法使用 `urllib.parse.quote` 進行了修正。
        # 注意：我們只對路徑的「部分」進行編碼，而不是整個 URL，以保留斜線分隔符。

        # 使用 quote 取代 as_posix() 來確保 URL 安全
        return f"/media/{encoded_path}"
    except (ValueError, TypeError):
        log.warning(f"無法將路徑 {absolute_path_str} 轉換為媒體 URL。回傳原始路徑。")
        return absolute_path_str


# --- API 端點 ---

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """根端點，提供 MPA 主頁面 (本機檔案轉錄)。"""
    html_file_path = STATIC_DIR / "mpa" / "index.html"
    if not html_file_path.is_file():
        log.error(f"找不到主頁檔案: {html_file_path}")
        raise HTTPException(status_code=404, detail="找不到主頁介面檔案 (index.html)")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)

@app.get("/downloader", response_class=HTMLResponse)
async def serve_downloader(request: Request):
    """提供媒體下載器頁面。"""
    html_file_path = STATIC_DIR / "mpa" / "downloader.html"
    if not html_file_path.is_file():
        log.error(f"找不到下載器檔案: {html_file_path}")
        raise HTTPException(status_code=404, detail="找不到下載器介面檔案 (downloader.html)")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)

@app.get("/youtube", response_class=HTMLResponse)
async def serve_youtube(request: Request):
    """
    提供 YouTube 報告頁面，並將後端常數注入為 JavaScript 物件。
    """
    html_file_path = STATIC_DIR / "mpa" / "youtube.html"
    if not html_file_path.is_file():
        log.error(f"找不到 YouTube 報告檔案: {html_file_path}")
        raise HTTPException(status_code=404, detail="找不到 YouTube 報告介面檔案 (youtube.html)")

    # 從 shared.constants 模組中提取所有大寫的常數
    task_constants = {name: value for name, value in inspect.getmembers(constants) if name.isupper()}
    constants_json = json.dumps(task_constants)

    html_content = html_file_path.read_text(encoding="utf-8")

    # 將常數作為一個 JavaScript 物件注入到 <head> 區塊中
    injection_script = f"<script>window.TASK_CONSTANTS = {constants_json};</script>"
    modified_html = html_content.replace("</head>", f"{injection_script}\n</head>")

    return HTMLResponse(content=modified_html, status_code=200)

@app.get("/simple_test", response_class=HTMLResponse)
async def serve_simple_test(request: Request):
    """提供一個極簡的 HTML 頁面，用於隔離測試前端事件監聽器。"""
    html_file_path = STATIC_DIR / "simple_test.html"
    if not html_file_path.is_file():
        raise HTTPException(status_code=404, detail="找不到 simple_test.html")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)

@app.get("/websocket_test", response_class=HTMLResponse)
async def serve_websocket_test(request: Request):
    """提供一個極簡的 HTML 頁面，用於除錯 WebSocket 原始訊息。"""
    html_file_path = STATIC_DIR / "mpa" / "websocket_test.html"
    if not html_file_path.is_file():
        raise HTTPException(status_code=404, detail="找不到 websocket_test.html")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)


async def check_model_exists(model_size: str) -> bool:
    """
    檢查指定的 Whisper 模型是否已經被下載到本地快取。(非同步版本)
    """
    # JULES'S FIX: 增加一個環境變數來強制使用模擬轉錄器，以支援混合模式測試
    force_mock = os.environ.get("FORCE_MOCK_TRANSCRIBER") == "true"
    tool_script_path = ROOT_DIR / "src" / "tools" / ("mock_transcriber.py" if IS_MOCK_MODE or force_mock else "transcriber.py")
    log.info(f"使用 '{tool_script_path}' 檢查模型 '{model_size}' 是否存在...")

    # 我們透過呼叫一個輕量級的工具腳本來檢查。
    check_command = [sys.executable, str(tool_script_path), "--command=check", f"--model_size={model_size}"]
    try:
        # 在模擬模式下，mock_transcriber.py 會永遠回傳 "exists"
        # JULES'S REFACTOR (2025-09-04): 改為非同步子程序呼叫
        process = await asyncio.create_subprocess_exec(
            *check_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            output = stdout.decode('utf-8').strip().lower()
            log.info(f"模型 '{model_size}' 檢查結果: {output}")
            # 必須完全匹配 "exists"，避免 "not_exists" 被錯誤判斷為 True
            return output == "exists"
        else:
            log.error(f"檢查模型 '{model_size}' 時發生錯誤: {stderr.decode('utf-8').strip()}")
            return False
    except FileNotFoundError as e:
        log.error(f"檢查模型 '{model_size}' 時發生錯誤 (指令不存在): {e}")
        return False

@app.post("/api/transcribe", status_code=202)
async def create_transcription_task(
    file: UploadFile = File(...),
    model_size: str = Form("tiny"),
    language: Optional[str] = Form(None),
    beam_size: int = Form(5)
):
    """
    接收上傳的音訊檔案，並為其建立一個 'pending' 狀態的轉錄任務。
    """
    task_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix or ".wav"
    saved_file_path = UPLOADS_DIR / f"{task_id}{file_extension}"

    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log.info(f"檔案已儲存至: {saved_file_path}")
    except Exception as e:
        log.error(f"❌ 儲存檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"無法儲存上傳的檔案: {e}")
    finally:
        await file.close()

    transcription_payload = {
        "input_file": str(saved_file_path),
        "original_filename": file.filename,
        "model_size": model_size,
        "language": language,
        "beam_size": beam_size
    }

    try:
        # --- 穩定性強化 ---
        # 將資料庫操作包在 try...except 區塊中，以捕捉連線錯誤。
        success = db_client.enqueue_task(task_id, json.dumps(transcription_payload), task_type='transcribe')
        if success:
            log.info(f"✅ 已成功為檔案 '{file.filename}' 建立轉錄任務: {task_id}")
            # 廣播一個新任務已建立的訊息，讓前端可以即時更新 UI
            await manager.broadcast_json({
                "type": "NEW_TASK_CREATED",
                "payload": {
                    "task_id": task_id,
                    "status": "pending",
                    "type": "transcribe",
                    "payload": transcription_payload
                }
            })
            return JSONResponse(
                status_code=202,
                content={"task_id": task_id, "type": "transcribe"}
            )
        else:
            # 這種情況表示 DB manager 正常連線，但回傳了 false
            log.error(f"❌ DB Manager 拒絕建立轉錄任務，檔案: '{file.filename}'。")
            raise HTTPException(status_code=500, detail="資料庫管理者拒絕建立任務。")
    except Exception as e:
        # 捕捉 db_client 可能拋出的任何例外 (例如 ConnectionRefusedError)
        log.critical(
            f"🚨 無法與 DB Manager 通訊以建立轉錄任務。請檢查 DB Manager 是否正在運行。錯誤: {e}",
            exc_info=True
        )
        # 返回一個標準的 JSON 錯誤，而不是讓伺服器崩潰。
        return JSONResponse(
            status_code=503, # Service Unavailable
            content={"detail": "後端資料庫服務暫時無法連線，請稍後再試。"}
        )


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

@app.get("/api/system/readiness")
async def system_readiness_check():
    """
    檢查核心依賴（如 yt-dlp）是否已準備就緒。
    """
    # 使用 shutil.which 檢查 yt-dlp 是否在系統 PATH 中且可執行
    yt_dlp_path = shutil.which("yt-dlp")
    is_ready = yt_dlp_path is not None

    if is_ready:
        log.info(f"✅ 系統就緒檢查：成功找到 yt-dlp 於 {yt_dlp_path}")
        return {"ready": True}
    else:
        log.warning("⚠️ 系統就緒檢查：找不到 yt-dlp。前端功能可能受限。")
        return {"ready": False}

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
        # JULES'S REFACTOR & FIX (2025-09-04): 改為非同步子程序呼叫，並修正縮排與邏輯錯誤
        process = await asyncio.create_subprocess_exec(
            'nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # 解析輸出
            gpu_usage = float(stdout.decode('utf-8').strip())
            gpu_detected = True
        else:
            # nvidia-smi 不存在或執行失敗
            log.debug(f"無法獲取 GPU 資訊: {stderr.decode('utf-8').strip()}")
    except FileNotFoundError:
        # 這個異常會在 'nvidia-smi' 命令本身不存在時觸發
        log.debug(f"無法獲取 GPU 資訊 (指令 'nvidia-smi' 不存在)")

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

    if task['status'] != '已完成':
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

        # JULES'S FIX 2025-08-14: 將 URL 路徑轉換回檔案系統絕對路徑
        # 資料庫中儲存的是像 /media/reports/report.html 這樣的 URL，
        # 我們需要將其轉換回像 /app/uploads/reports/report.html 這樣的絕對檔案系統路徑。
        if output_filename.startswith('/media/'):
            # 移除 '/media/' 前綴並與上傳目錄合併
            relative_path = output_filename.lstrip('/media/')
            # JULES'S FIX 2025-08-31: 新增 URL 解碼步驟
            # 這是解決「檔案名稱過長」錯誤的關鍵。從資料庫取出的路徑是
            # URL 編碼過的 (例如 'file%20name.txt')，我們必須將其解碼回
            # 'file name.txt' 才能讓檔案系統找到它。
            decoded_relative_path = unquote(relative_path)
            file_path = UPLOADS_DIR / decoded_relative_path
        else:
            # 作為備用，如果路徑不是 /media/ 開頭，則假設它是一個絕對路徑
            # 這可以保持對舊資料格式的相容性
            file_path = Path(output_filename)

        if not file_path.is_file():
            log.error(f"❌ 檔案系統中的檔案不存在: {file_path}")
            raise HTTPException(status_code=404, detail="檔案遺失或無法讀取。")

        # 提供檔案下載
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            media_type = 'application/pdf'
        elif ext == '.html':
            media_type = 'text/html'
        elif ext == '.mp4':
            media_type = 'video/mp4'
        elif ext in ['.mp3', '.m4a', '.wav', '.flac']:
            media_type = f'audio/{ext.strip(".")}'
        else:
            media_type = 'text/plain'
        return FileResponse(path=file_path, filename=file_path.name, media_type=media_type)

    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"❌ 解析任務 {task_id} 的結果時出錯: {e}")
        raise HTTPException(status_code=500, detail="無法解析任務結果。")


@app.post("/api/rename/{task_id}", status_code=200)
async def rename_task_file(task_id: str, request: Request):
    """
    重新命名與已完成任務關聯的檔案。
    """
    log.info(f"收到重新命名任務 {task_id} 的請求。")
    try:
        data = await request.json()
        new_filename_base = data.get("new_filename")
        if not new_filename_base:
            raise HTTPException(status_code=400, detail="請求中未提供 'new_filename'。")

        task = db_client.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="找不到指定的任務 ID。")
        if task['status'] != '已完成':
            raise HTTPException(status_code=400, detail="只能重新命名已完成的任務。")

        result_data = json.loads(task['result'])
        old_path_str = result_data.get("output_path")
        if not old_path_str:
            raise HTTPException(status_code=500, detail="任務結果中找不到檔案路徑。")

        # JULES DEBUG (2025-08-31): 根據最新分析報告，此處是造成重新命名失敗的關鍵。
        # old_path_str 是一個 URL 路徑 (例如 /media/file.mp4)，而不是檔案系統路徑。
        # 我們需要將其轉換回絕對檔案系統路徑 (例如 /app/uploads/file.mp4)。
        if old_path_str.startswith('/media/'):
            # 移除 '/media/' 前綴並與上傳目錄合併
            relative_path = old_path_str.lstrip('/media/')
            # 這裡需要對 relative_path 進行 URL 解碼，以處理檔名中的 %20 等字元
            decoded_relative_path = unquote(relative_path)
            old_path = UPLOADS_DIR / decoded_relative_path
        else:
            # 作為備用，如果路徑不是 /media/ 開頭，則假設它是一個絕對路徑
            old_path = Path(old_path_str)

        file_extension = old_path.suffix
        new_path = old_path.with_name(f"{new_filename_base}{file_extension}")

        if old_path == new_path:
            return {"status": "success", "message": "新舊檔名相同，無需變更。", "new_filename": new_filename_base}

        if new_path.exists():
            raise HTTPException(status_code=409, detail=f"目標檔名 {new_path.name} 已存在。")

        os.rename(old_path, new_path)
        log.info(f"檔案已從 {old_path} 重新命名為 {new_path}")

        # 更新資料庫中的結果
        # JULES DEBUG (2025-08-31): 重新命名後，我們需要將新的「檔案系統路徑」轉換回「媒體 URL」，
        # 然後再存入資料庫，以保持資料格式的一致性。
        result_data["output_path"] = convert_to_media_url(str(new_path))
        result_data["video_title"] = new_filename_base

        db_client.update_task_status(task_id, '已完成', json.dumps(result_data))
        log.info(f"已更新資料庫中任務 {task_id} 的結果。")

        return {"status": "success", "message": "檔案重新命名成功。", "new_filename": new_filename_base}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="無法解析任務結果。")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="找不到要重新命名的原始檔案。")
    except Exception as e:
        log.error(f"❌ 重新命名檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤: {e}")


# --- 提示詞管理 API ---
PROMPTS_FILE_PATH = ROOT_DIR / "src" / "prompts" / "default_prompts.json"

@app.get("/api/prompts")
async def get_prompts():
    """讀取並回傳 prompts/default_prompts.json 的內容。"""
    if not PROMPTS_FILE_PATH.is_file():
        log.error(f"提示詞檔案遺失: {PROMPTS_FILE_PATH}")
        raise HTTPException(status_code=404, detail="提示詞設定檔 (default_prompts.json) 找不到。")
    try:
        with open(PROMPTS_FILE_PATH, 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        return JSONResponse(content=prompts)
    except Exception as e:
        log.error(f"讀取或解析提示詞檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="無法讀取或解析提示詞檔案。")

@app.post("/api/prompts")
async def save_prompts(request: Request):
    """接收前端傳來的 JSON 並儲存至 prompts/default_prompts.json。"""
    try:
        new_prompts = await request.json()
        # 進行基本的驗證，確保它是一個字典
        if not isinstance(new_prompts, dict):
            raise HTTPException(status_code=400, detail="無效的資料格式，應為 JSON 物件。")

        with open(PROMPTS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(new_prompts, f, ensure_ascii=False, indent=4)

        log.info(f"✅ 提示詞已成功儲存至: {PROMPTS_FILE_PATH}")
        return {"status": "success", "message": "提示詞已成功更新。"}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="請求內容不是有效的 JSON 格式。")
    except Exception as e:
        log.error(f"儲存提示詞檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"儲存提示詞檔案時發生伺服器內部錯誤: {e}")


@app.post("/api/upload_cookies", status_code=200)
async def upload_cookies_file(file: UploadFile = File(...)):
    """
    接收使用者上傳的 cookies.txt 檔案並儲存。
    """
    if "cookies.txt" not in file.filename.lower():
        raise HTTPException(status_code=400, detail="檔案名稱必須是 'cookies.txt' 或包含該字樣。")

    cookies_path = UPLOADS_DIR / "cookies.txt"
    try:
        with open(cookies_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log.info(f"🍪 Cookies 檔案已儲存至: {cookies_path}")
        return {"status": "success", "message": "Cookies 檔案上傳成功。"}
    except Exception as e:
        log.error(f"❌ 儲存 Cookies 檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"無法儲存 Cookies 檔案: {e}")
    finally:
        await file.close()


# --- YouTube 功能相關 API ---

@app.post("/api/youtube/validate_api_key")
async def validate_api_key(request: Request):
    """接收前端傳來的 API Key 並進行驗證。"""
    try:
        payload = await request.json()
        api_key = payload.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400, detail="未提供 API 金鑰。")

        if IS_MOCK_MODE:
            log.info("模擬模式：將非空 API 金鑰視為有效。")
            return {"valid": True}

        tool_script_path = ROOT_DIR / "src" / "tools" / "gemini_processor.py"
        cmd = [sys.executable, str(tool_script_path), "--command=validate_key"]

        # JULES'S FIX V3: 建立一個最小化的乾淨環境來執行驗證。
        # 這是為了防止 Google 的函式庫自動從沙箱環境中繼承任何「應用程式預設憑證」，
        # 從而確保驗證過程只使用使用者提供的 API 金鑰。
        minimal_env = {
            "PATH": os.environ.get("PATH", ""),
            "GOOGLE_API_KEY": api_key,
            # JULES'S FIX (2025-09-04): 根據交接報告，此處是造成 API 金鑰驗證失敗的直接原因。
            # 必須將專案的 src 目錄加入 PYTHONPATH，子程序 gemini_processor.py 才能正確匯入其依賴的本地模組。
            "PYTHONPATH": str(SRC_DIR),
            # 在某些系統上，特別是 Windows，需要 SYSTEMROOT。為保險起見加入。
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")
        }

        # JULES'S REFACTOR (2025-09-04): 將阻塞的 subprocess.run 改為非同步的 asyncio.create_subprocess_exec
        # 這是為了解決 `subprocess.run` 會阻塞整個 FastAPI 事件迴圈的問題，此問題會導致嚴重的效能瓶頸和超時錯誤。
        # 新的方法會以非同步的方式執行子程序，讓伺服器在等待子程序完成時仍能處理其他請求。
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=minimal_env
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            log.info(f"API 金鑰驗證成功。")
            return {"valid": True}
        else:
            # 將 stderr 從 bytes 解碼為 utf-8 字串
            error_message = stderr.decode('utf-8').strip()
            log.warning(f"API 金鑰驗證失敗。Stderr: {error_message}")
            detail = error_message if error_message else "金鑰驗證失敗，請檢查主控台日誌以了解詳情。"
            return JSONResponse(status_code=400, content={"valid": False, "detail": detail})

    except Exception as e:
        log.error(f"驗證 API 金鑰時發生伺服器內部錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"伺服器內部錯誤: {e}")


class ApiKeyPayload(BaseModel):
    api_key: str

@app.post("/api/youtube/models")
async def get_youtube_models(payload: ApiKeyPayload):
    """
    獲取可用的 Gemini 模型列表。
    現在接收一個包含 API 金鑰的 POST 請求。
    """
    # 在模擬模式下，回傳一個固定的假列表
    if os.environ.get("API_MODE") == "mock":
        return {
            "models": [
                {"id": "gemini-pro-mock", "name": "Gemini Pro (模擬)"},
                {"id": "gemini-1.5-flash-mock", "name": "Gemini 1.5 Flash (模擬)"}
            ]
        }

    # 真實模式下，從 gemini_processor.py 獲取
    try:
        if not payload.api_key:
            raise HTTPException(status_code=400, detail="請求中未提供 API 金鑰。")

        log.info(f"收到來自前端的 API 金鑰，將其用於獲取模型列表。")

        tool_script_path = ROOT_DIR / "src" / "tools" / "gemini_processor.py"
        cmd = [sys.executable, str(tool_script_path), "--command=list_models"]

        # JULES'S FIX V4 (2025-09-04): 根據 E2E 測試再次失敗的分析，問題比預想的更深。
        # `os.environ.copy()` 會繼承父程序的所有環境變數，其中可能包含與 Google Cloud 相關的
        # 其他身份驗證資訊 (例如 GCE_METADATA_HOST, GOOGLE_APPLICATION_CREDENTIALS 等)，
        # 這些變數可能會干擾或覆蓋我們明確設定的 GOOGLE_API_KEY。
        #
        # `validate_api_key` 函數之所以能成功，正是因為它使用了一個「最小化的乾淨環境」。
        # 我們現在將相同的策略應用到這裡，以確保子程序在一個可預測的、乾淨的環境中執行，
        # 只使用我們提供的 API 金鑰進行身份驗證。
        minimal_env = {
            "PATH": os.environ.get("PATH", ""),
            "GOOGLE_API_KEY": payload.api_key,
            "PYTHONPATH": str(SRC_DIR),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "") # 在 Windows 上可能需要
        }

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=minimal_env
        )
        stdout, stderr = await process.communicate()

        # JULES'S DEBUGGING (2025-09-04): 加入強制日誌記錄以進行根本原因分析
        stdout_log = stdout.decode('utf-8').strip()
        stderr_log = stderr.decode('utf-8').strip()
        log.info(f"--- Subprocess Output for 'list_models' ---")
        log.info(f"Return Code: {process.returncode}")
        log.info(f"Stdout: {stdout_log}")
        log.info(f"Stderr: {stderr_log}")
        log.info(f"-------------------------------------------")


        if process.returncode == 0:
            models = json.loads(stdout_log)
            return {"models": models}
        else:
            log.error(f"獲取 Gemini 模型列表失敗，可能是因為 API 金鑰無效。Stderr: {stderr_log}")
            # 將更詳細的錯誤訊息傳回給前端
            if "API Key not found" in stderr_log:
                detail_message = "API 金鑰遺失。請確認後端已正確接收金鑰。"
            elif "API key not valid" in stderr_log:
                detail_message = "API 金鑰無效。請檢查您的金鑰。"
            else:
                detail_message = f"無法使用提供的 API 金鑰獲取模型列表，請檢查金鑰權限或網路連線。詳細資訊: {stderr_log}"
            raise HTTPException(status_code=401, detail=detail_message)
    except Exception as e:
        log.error(f"獲取 Gemini 模型列表時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="無法獲取 Gemini 模型列表。")


async def _create_processing_tasks(payload: dict):
    """
    [JULES'S REFACTOR - 2025-09-08]
    將建立任務的核心邏輯提取到此輔助函式中，以供多個 API 端點重複使用。
    """
    requests_list = payload.get("requests", [])

    # JULES'S FIX: 為了相容舊的 local_run.py 測試腳本
    if not requests_list and "urls" in payload:
        log.warning("偵測到舊版的 'urls' 負載格式，正在進行相容處理。")
        requests_list = [{"url": url, "filename": None} for url in payload.get("urls", [])]

    # 新的彈性參數
    model = payload.get("model")
    tasks_to_run = payload.get("tasks", "summary,transcript")
    output_format = payload.get("output_format", "html")
    download_only = payload.get("download_only", False)
    download_type = payload.get("download_type", "audio")
    api_key = payload.get("api_key")

    if not requests_list:
        raise HTTPException(status_code=400, detail="請求中必須包含 'requests' 或 'urls'。")
    if not download_only and not model:
        raise HTTPException(status_code=400, detail="執行 AI 分析時必須提供 'model'。")
    if not download_only and not api_key:
        raise HTTPException(status_code=401, detail="執行 AI 分析時必須提供 'api_key'。")

    tasks_created = []
    try:
        for req_item in requests_list:
            url = req_item.get("url")
            filename = req_item.get("filename")

            if not url or not url.strip():
                continue

            task_id = str(uuid.uuid4())

            if download_only:
                task_payload = {"url": url, "output_dir": str(UPLOADS_DIR), "custom_filename": filename, "download_type": download_type}
                success = db_client.enqueue_task(task_id, json.dumps(task_payload), task_type='youtube_download_only')
                if success:
                    task_info = {"url": url, "task_id": task_id, "type": "youtube_download_only", "payload": task_payload}
                    tasks_created.append(task_info)
                    await manager.broadcast_json({"type": "NEW_TASK_CREATED", "payload": {**task_info, "status": "pending"}})
                else:
                    log.error(f"❌ DB Manager 拒絕為 URL '{url}' 建立僅下載任務。")

            else:
                download_task_id = task_id
                process_task_id = str(uuid.uuid4())

                download_payload = {"url": url, "output_dir": str(UPLOADS_DIR), "custom_filename": filename, "download_type": "audio"}
                process_payload = {
                    "model": model,
                    "tasks": tasks_to_run,
                    "output_format": output_format,
                    "api_key": api_key
                }

                dl_success = db_client.enqueue_task(download_task_id, json.dumps(download_payload), task_type='youtube_download')
                if dl_success:
                    dl_task_info = {"url": url, "task_id": download_task_id, "type": "youtube_download", "payload": download_payload}
                    tasks_created.append(dl_task_info)

                    proc_success = db_client.enqueue_task(process_task_id, json.dumps(process_payload), task_type='gemini_process', depends_on=download_task_id)
                    if proc_success:
                        proc_task_info = {
                            "url": url,
                            "task_id": download_task_id, # 前端是根據這個 ID 來追蹤
                            "final_task_id": process_task_id,
                            "type": "gemini_process",
                            "depends_on": download_task_id,
                            "payload": process_payload
                        }
                        tasks_created.append(proc_task_info)
                        await manager.broadcast_json({"type": "NEW_TASK_CREATED", "payload": {**proc_task_info, "status": "pending"}})
                    else:
                        log.error(f"❌ DB Manager 拒絕為 URL '{url}' 建立 Gemini 處理任務。")
                else:
                    log.error(f"❌ DB Manager 拒絕為 URL '{url}' 建立下載任務。")

        return JSONResponse(content={"message": f"已為 {len(requests_list)} 個 URL 建立 {len(tasks_created)} 個處理任務。", "tasks": tasks_created})
    except Exception as e:
        log.critical(
            f"🚨 在建立 YouTube 任務過程中無法與 DB Manager 通訊。請檢查 DB Manager 是否正在運行。錯誤: {e}",
            exc_info=True
        )
        # 返回一個標準的 JSON 錯誤，而不是讓伺服器崩潰。
        return JSONResponse(
            status_code=503, # Service Unavailable
            content={"detail": "後端資料庫服務暫時無法連線，請稍後再試。"}
        )


@app.post("/api/download/start", status_code=202)
async def start_download_task(request: Request):
    """
    [JULES'S FIX - 2025-09-08]
    根據分析報告，新增此端點以處理前端發送的 POST /api/download/start 請求 (405 錯誤)。
    此端點會將請求轉換並呼叫共用的任務建立邏輯。
    """
    log.info("接收到來自 /api/download/start 的舊版下載請求，正在進行轉發處理...")
    payload = await request.json()
    urls = payload.get("urls", [])
    if not urls:
        raise HTTPException(status_code=400, detail="請求中必須包含 'urls' 列表。")

    compatible_payload = {
        "requests": [{"url": url, "filename": ""} for url in urls],
        "download_only": True,
        "download_type": payload.get("download_type", "audio"),
    }
    return await _create_processing_tasks(compatible_payload)


@app.post("/api/youtube/process", status_code=202)
async def process_youtube_urls(request: Request):
    """
    接收 YouTube URL，並根據前端傳來的參數，建立對應的下載和 AI 分析任務。
    現在這個函式只是一個包裝器，核心邏輯在 _create_processing_tasks 中。
    """
    payload = await request.json()
    return await _create_processing_tasks(payload)


@app.post("/api/debug/clear_tasks", status_code=200)
async def clear_all_tasks_endpoint():
    """
    [僅供測試] 清除所有任務，用於重置測試環境。
    """
    log.warning("⚠️ [僅供測試] 收到請求，將清除所有任務...")
    try:
        success = db_client.clear_all_tasks()
        if success:
            return {"status": "success", "message": "所有任務已成功清除。"}
        else:
            raise HTTPException(status_code=500, detail="在伺服器端清理任務時發生錯誤。")
    except Exception as e:
        log.error(f"❌ 清理任務的 API 端點發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
            # 在這個新的架構中，WebSocket 主要用於從伺服器向客戶端廣播更新。
            # 我們仍然可以保留接收訊息的迴圈，以備未來雙向通訊的需求 (例如 ping/pong)。
            data = await websocket.receive_text()
            log.info(f"從 WebSocket 收到訊息: {data}")
            # 目前，我們只記錄收到的訊息，不做任何處理。
            await manager.send_personal_message(f"訊息已收到: {data}", websocket)

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


class AppStatePayload(BaseModel):
    key: str
    value: str

@app.post("/api/app_state", status_code=200)
async def set_app_state_endpoint(payload: AppStatePayload):
    """
    設定一個應用程式狀態值。
    """
    try:
        success = db_client.set_app_state(payload.key, payload.value)
        if success:
            # 廣播狀態變更
            await manager.broadcast_json({"type": "APP_STATE_UPDATE", "payload": {payload.key: payload.value}})
            return {"status": "success", "key": payload.key, "value": payload.value}
        else:
            raise HTTPException(status_code=500, detail="無法在資料庫中設定應用程式狀態。")
    except Exception as e:
        log.error(f"❌ 設定應用程式狀態時 API 出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="設定應用程式狀態時發生內部錯誤。")

@app.get("/api/app_state", response_class=JSONResponse)
async def get_all_app_states_endpoint():
    """
    獲取所有應用程式狀態值。
    """
    try:
        states = db_client.get_all_app_states()
        return JSONResponse(content=states)
    except Exception as e:
        log.error(f"❌ 獲取所有應用程式狀態時 API 出錯: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="獲取所有應用程式狀態時發生內部錯誤。")


@app.post("/api/internal/notify_task_update", status_code=200)
async def notify_task_update(request: Request):
    """
    一個內部端點，供 Worker 程序在任務更新時呼叫。
    此端點會從資料庫獲取最新的任務狀態，並透過 WebSocket 廣播給前端。
    """
    payload = await request.json()
    task_id = payload.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="請求中缺少 'task_id'。")

    log.info(f"🔔 收到來自 Worker 的任務更新通知: Task {task_id}")

    # 從資料庫獲取權威的最新任務狀態
    task_info = db_client.get_task_status(task_id)
    if not task_info:
        log.error(f"收到無效任務 ID '{task_id}' 的通知，無法廣播。")
        raise HTTPException(status_code=404, detail=f"找不到任務 ID: {task_id}")

    task_type = task_info.get("type", "transcribe")
    message_type = "TRANSCRIPTION_STATUS"
    if "youtube" in task_type or "gemini" in task_type:
        message_type = "YOUTUBE_STATUS"

    # 解析 result 欄位（如果存在）
    if task_info.get("result") and isinstance(task_info["result"], str):
        try:
            task_info["result"] = json.loads(task_info["result"])
        except json.JSONDecodeError:
            log.warning(f"任務 {task_id} 的 DB 結果不是有效的 JSON，將以字串形式廣播。")

    log.info(f"根據任務類型 '{task_type}'，將使用 WebSocket 訊息類型: '{message_type}' 進行廣播。")

    # 廣播從資料庫中讀取的完整、權威的任務資訊
    message = {"type": message_type, "payload": task_info}
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
    parser.add_argument("--mock", action="store_true", help="Run in mock mode.")
    args, _ = parser.parse_known_args()

    # JULES'S FIX (2025-09-05): Use the --mock flag to set the environment variable
    # for this process, ensuring IS_MOCK_MODE is set correctly.
    if args.mock:
        os.environ["API_MODE"] = "mock"

    log.info("🚀 啟動 API 伺服器 (v3)...")
    log.info(f"請在瀏覽器中開啟 http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
