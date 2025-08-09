# api_server.py
import uuid
import shutil
import logging
import json
import subprocess
import sys
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, Dict

# 匯入新的資料庫模組
from db import database

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('api_server')

# --- FastAPI 應用實例 ---
app = FastAPI(title="鳳凰音訊轉錄儀 API (v3 - 重構)", version="3.0")

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
    這是一個簡化的實現，依賴於 `tools/transcriber.py` 的能力。
    """
    # 為了避免在 API Server 中直接依賴 heavy ML 函式庫，
    # 我們透過呼叫一個輕量級的工具腳本來檢查。
    check_command = [sys.executable, "tools/transcriber.py", "--command=check", f"--model_size={model_size}"]
    try:
        result = subprocess.run(check_command, capture_output=True, text=True, check=True)
        log.info(f"模型 '{model_size}' 檢查結果: {result.stdout.strip()}")
        return "exists" in result.stdout.lower()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.error(f"檢查模型 '{model_size}' 時發生錯誤: {e}")
        return False

@app.post("/api/transcribe", status_code=202)
async def create_transcription_task(
    file: UploadFile = File(...),
    model_size: str = Form("tiny"),
    language: Optional[str] = Form(None)
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
        "output_dir": "transcripts",
        "model_size": model_size,
        "language": language
    }

    if model_is_present:
        # 模型已存在，直接建立轉錄任務
        log.info(f"✅ 模型 '{model_size}' 已存在，直接建立轉錄任務: {transcribe_task_id}")
        database.add_task(transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe')
        return {"task_id": transcribe_task_id}
    else:
        # 模型不存在，建立下載任務和依賴的轉錄任務
        download_task_id = str(uuid.uuid4())
        log.warning(f"⚠️ 模型 '{model_size}' 不存在。建立下載任務 '{download_task_id}' 和依賴的轉錄任務 '{transcribe_task_id}'")

        download_payload = {"model_size": model_size}
        database.add_task(download_task_id, json.dumps(download_payload), task_type='download')

        database.add_task(transcribe_task_id, json.dumps(transcription_payload), task_type='transcribe', depends_on=download_task_id)

        # 我們回傳轉錄任務的 ID，讓前端可以追蹤最終結果
        return JSONResponse(content={"tasks": [
            {"task_id": download_task_id, "type": "download"},
            {"task_id": transcribe_task_id, "type": "transcribe"}
        ]})


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """
    根據任務 ID，從資料庫查詢任務狀態。
    """
    log.debug(f"🔍 正在查詢任務狀態: {task_id}")
    status_info = database.get_task_status(task_id)

    if not status_info:
        log.warning(f"❓ 找不到任務 ID: {task_id}")
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID")

    # 將資料庫回傳的 Row 物件轉換為字典
    response_data = dict(status_info)

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


@app.post("/log/action", status_code=200)
async def log_frontend_action(payload: Dict):
    """
    接收前端發送的操作日誌。
    """
    log.info(f"📝 收到前端操作日誌: {payload}")
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


@app.get("/api/health")
async def health_check():
    """提供一個簡單的健康檢查端點。"""
    return {"status": "ok", "message": "API Server is running."}

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
    args = parser.parse_args()

    log.info("🚀 啟動 API 伺服器 (v3)...")
    # 初始化資料庫
    database.initialize_database()
    log.info(f"請在瀏覽器中開啟 http://127.0.0.1:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
