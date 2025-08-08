# app/main.py
import uuid
import shutil
import logging
import sys
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 將專案根目錄加入 sys.path 以便匯入 phoenix_runner
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
import phoenix_runner

# --- 日誌設定 ---
# 為此模組建立一個專用的 logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('api')

# --- FastAPI 應用實例 ---
app = FastAPI(title="鳳凰音訊轉錄儀 API (v2 - 解耦架構)", version="2.0")

# --- 路徑設定 ---
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
# 新的、基於檔案系統的任務佇列目錄
TASKS_PENDING_DIR = BASE_DIR / "tasks_pending"
TASKS_COMPLETED_DIR = BASE_DIR / "tasks_completed"

# 確保目錄存在
STATIC_DIR.mkdir(exist_ok=True)
TASKS_PENDING_DIR.mkdir(exist_ok=True)
TASKS_COMPLETED_DIR.mkdir(exist_ok=True)

# --- 掛載靜態檔案 ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- API 端點 ---

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """根端點，提供前端操作介面。"""
    html_file_path = STATIC_DIR / "mp3.html"
    if not html_file_path.is_file():
        raise HTTPException(status_code=500, detail="找不到前端檔案 (mp3.html)")
    return HTMLResponse(content=html_file_path.read_text(encoding="utf-8"), status_code=200)


@app.post("/api/transcribe", status_code=202)
async def create_transcription_task(
    file: UploadFile = File(...),
    model_size: str = Form("tiny"),
    language: str = Form(None)
):
    """
    接收音訊檔案，建立一個轉錄任務，並觸發背景工作。
    """
    task_id = str(uuid.uuid4())
    log.info(f"📥 收到新的轉錄請求，分配任務 ID: {task_id}")

    # 定義輸入和輸出檔案的路徑
    # 注意：我們現在直接使用 task_id 作為檔名，副檔名保留
    file_extension = Path(file.filename).suffix if Path(file.filename).suffix else ".wav"
    input_file_path = TASKS_PENDING_DIR / f"{task_id}{file_extension}"
    output_file_path = TASKS_COMPLETED_DIR / f"{task_id}.txt"

    # 儲存上傳的檔案
    try:
        with open(input_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log.info(f"檔案已儲存至: {input_file_path}")
    except Exception as e:
        log.error(f"❌ 儲存檔案時發生錯誤: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"無法儲存上傳的檔案: {e}")
    finally:
        await file.close()

    # 使用 phoenix_runner 啟動背景工作
    try:
        phoenix_runner.run(
            tool_name="transcriber",
            args=[str(input_file_path), str(output_file_path), f"--model_size={model_size}", f"--language={language}"],
            mock=True  # 在這個開發環境中，我們總是使用模擬工具
        )
        log.info(f"✅ 任務 {task_id} 已成功委派給 Phoenix Runner。")
    except phoenix_runner.ToolExecutionError as e:
        log.error(f"❌ 委派任務給 Phoenix Runner 時失敗: {e}", exc_info=True)
        # 如果委派失敗，我們應該清理已上傳的檔案
        input_file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"無法啟動背景工作: {e}")

    return {"task_id": task_id}


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """
    根據任務 ID，透過檢查檔案系統來回報任務狀態。
    """
    log.debug(f"🔍 正在查詢任務狀態: {task_id}")

    output_file = TASKS_COMPLETED_DIR / f"{task_id}.txt"
    error_file = TASKS_COMPLETED_DIR / f"{task_id}.error"

    # 為了找到原始輸入檔案，我們需要掃描 pending 目錄
    # 這不是最高效的，但在這個架構下是可行的
    pending_files = list(TASKS_PENDING_DIR.glob(f"{task_id}.*"))
    is_pending = any(pending_files)

    if output_file.exists():
        log.info(f"✅ 任務 {task_id} 已完成。")
        return {
            "id": task_id,
            "status": "COMPLETED",
            "result": output_file.read_text(encoding='utf-8')
        }
    elif error_file.exists():
        log.error(f"❌ 任務 {task_id} 已失敗。")
        return {
            "id": task_id,
            "status": "FAILED",
            "error": error_file.read_text(encoding='utf-8')
        }
    elif is_pending:
        log.info(f"⏳ 任務 {task_id} 仍在處理中。")
        return {"id": task_id, "status": "PROCESSING"}
    else:
        log.warning(f"❓ 找不到任務 {task_id} 的任何相關檔案。")
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID")


@app.get("/api/health")
async def health_check():
    """提供一個簡單的健康檢查端點。"""
    return {"status": "ok"}

# --- 主程式啟動 ---
if __name__ == "__main__":
    import uvicorn
    log.info("🚀 啟動 FastAPI 伺服器...")
    log.info("請在瀏覽器中開啟 http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
