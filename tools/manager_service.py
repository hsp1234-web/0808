import subprocess
import sys
import os
import time
import json
import uuid
import shutil
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File, BackgroundTasks

# --- 組態設定 ---
# 所有路徑皆相對於專案根目錄
LOG_FILE_PATH = Path("storage/dashboard.log")
TASK_BASE_DIR = Path("storage/tasks")
UPLOADS_DIR = Path("storage/uploads")

PENDING_DIR = TASK_BASE_DIR / "pending"
PROCESSING_DIR = TASK_BASE_DIR / "processing"
COMPLETED_DIR = TASK_BASE_DIR / "completed"
FAILED_DIR = TASK_BASE_DIR / "failed"

TOOL_TO_RUN = Path("tools/transcription_tool.py")

# --- FastAPI 應用程式 ---
app = FastAPI(title="鳳凰之心 - 管理器服務")

# --- 日誌設定 ---
def setup_logging():
    """設定共享日誌檔案。腳本啟動時會清除舊日誌。"""
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
        f.write("")

def log_message(message: str):
    """將帶有時間戳的訊息附加到共享日誌檔案中。"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"[{timestamp}] [ManagerService] {message}\n"
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(full_message)
    print(full_message, end="") # 同時也打印到自身的 stdout

# --- 核心邏輯 ---
def run_tool_process(script_path: Path, tool_name: str):
    """
    以子程序形式執行一個工具，並將其輸出串流至日誌檔案。
    這是一個阻塞函式，設計為在背景任務中運行。
    """
    log_message(f"背景任務：開始執行工具 '{tool_name}'...")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1,
        universal_newlines=True,
        env=env
    )

    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(line)
            print(line, end="")

    process.wait()
    log_message(f"背景任務：工具 '{tool_name}' 執行完畢，返回碼為 {process.returncode}。")
    if process.stdout:
        process.stdout.close()

# --- API 端點 ---
@app.get("/")
async def root():
    return {"message": "鳳凰之心 - 管理器服務已上線"}

@app.post("/api/v1/transcribe")
async def create_transcription_task(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    接收音訊檔案上傳，建立轉錄任務，並在背景啟動工具。
    """
    log_message(f"API：收到檔案上傳請求: {file.filename}")

    task_id = str(uuid.uuid4())
    original_filename = Path(file.filename).name
    saved_filepath = UPLOADS_DIR / f"{task_id}_{original_filename}"

    # 1. 儲存上傳的檔案
    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        with saved_filepath.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        log_message(f"API：檔案已儲存至 {saved_filepath}")
    except Exception as e:
        log_message(f"API 錯誤：儲存檔案失敗: {e}")
        return {"status": "error", "message": "Failed to save uploaded file."}
    finally:
        file.file.close()

    # 2. 建立任務信件
    task_data = {
        "task_id": task_id,
        "type": "transcription",
        "original_filename": original_filename,
        "file_path": str(saved_filepath),
        "created_at": time.time()
    }
    task_filepath = PENDING_DIR / f"{task_id}.json"
    try:
        with open(task_filepath, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, indent=4)
        log_message(f"API：任務信件已建立: {task_filepath.name}")
    except Exception as e:
        log_message(f"API 錯誤：建立任務信件失敗: {e}")
        return {"status": "error", "message": "Failed to create task file."}

    # 3. 在背景啟動消費者工具
    background_tasks.add_task(run_tool_process, TOOL_TO_RUN, "transcription_tool")
    log_message(f"API：已排程背景任務以啟動轉錄工具。")

    return {
        "status": "success",
        "message": "Task created successfully",
        "task_id": task_id
    }

@app.post("/api/v1/run-etl", status_code=202)
async def run_prometheus_etl(background_tasks: BackgroundTasks):
    """
    建立一個任務來運行 Prometheus ETL 管線。
    """
    log_message("API：收到運行 Prometheus ETL 管線的請求。")

    task_id = str(uuid.uuid4())

    # 在此範例中，我們假設原始資料位於一個預定義的位置。
    source_data_directory = "storage/prometheus/raw_data"

    task_data = {
        "task_id": task_id,
        "type": "prometheus_etl",
        "source_dir": source_data_directory,
        "created_at": time.time()
    }
    # 為此任務類型使用一個獨特的名稱
    task_filepath = PENDING_DIR / f"prometheus_etl_{task_id}.json"

    try:
        with open(task_filepath, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, indent=4)
        log_message(f"API：Prometheus ETL 任務已建立: {task_filepath.name}")
    except Exception as e:
        log_message(f"API 錯誤：建立 Prometheus ETL 任務檔案失敗: {e}")
        return {"status": "error", "message": "Failed to create ETL task file."}

    # 在背景啟動 prometheus 管線工具
    prometheus_tool_path = Path("tools/prometheus_pipeline_tool.py")
    background_tasks.add_task(run_tool_process, prometheus_tool_path, "prometheus_pipeline_tool")
    log_message(f"API：已排程背景任務以運行 prometheus_pipeline_tool。")

    return {
        "status": "success",
        "message": "Prometheus ETL task created and scheduled successfully",
        "task_id": task_id
    }

# --- 主進入點 ---
def main():
    """
    主進入點：設定日誌並啟動 Uvicorn 伺服器。
    """
    setup_logging()
    log_message("服務即將啟動...")

    # 確保所有需要的目錄都存在
    for d in [PENDING_DIR, PROCESSING_DIR, COMPLETED_DIR, FAILED_DIR, UPLOADS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    log_message("Uvicorn 伺服器正在 0.0.0.0:8000 上啟動...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
