# app/main.py
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 匯入我們共享的佇列和結果儲存區
from .queue import task_queue
from . import result_store

# 建立 FastAPI 應用實例
app = FastAPI(title="鳳凰音訊轉錄儀 API", version="1.0")

# 取得目前檔案的絕對路徑
BASE_DIR = Path(__file__).resolve().parent

# 掛載 static 資料夾
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 建立一個用於存放上傳檔案的臨時目錄
UPLOADS_DIR = BASE_DIR / "temp_uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """根端點，提供前端操作介面。"""
    html_file_path = BASE_DIR / "static" / "mp3.html"
    try:
        with open(html_file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="找不到前端檔案 (mp3.html)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取前端檔案時發生錯誤: {e}")


@app.post("/api/transcribe", status_code=202)
async def enqueue_transcription_task(file: UploadFile = File(...)):
    """
    接收音訊檔案，將轉錄任務放入佇列，並立即返回一個任務 ID。
    這是一個非阻塞的端點。
    """
    try:
        # 產生一個唯一的任務 ID
        task_id = str(uuid.uuid4())

        # 確保檔名安全，並建立檔案儲存路徑
        # 在真實應用中，應對檔名做更嚴格的清理
        safe_filename = Path(file.filename).name
        file_path = UPLOADS_DIR / f"{task_id}_{safe_filename}"

        # 儲存上傳的檔案
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 在結果儲存區中初始化任務狀態
        result_store.set_status(task_id, "pending")

        # 將任務（ID 和檔案路徑）放入佇列
        task_queue.put((task_id, str(file_path)))

        print(f"✅ [API] 新任務已加入佇列 (ID: {task_id})")

        # 立即返回任務 ID，讓前端可以開始輪詢
        return {"task_id": task_id}

    except Exception as e:
        print(f"❌ [API] 將任務加入佇列時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail=f"無法處理您的請求: {e}")
    finally:
        await file.close()


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """
    根據任務 ID 查詢任務的目前狀態和結果。
    """
    status_info = result_store.get_status(task_id)

    if status_info is None:
        raise HTTPException(status_code=404, detail="找不到指定的任務 ID")

    return JSONResponse(content=status_info)


# 為了讓 Colab 或其他啟動器可以直接執行，我們可以加入這段
if __name__ == "__main__":
    import uvicorn
    print("若要啟動伺服器，請在終端機中執行：")
    print("uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
