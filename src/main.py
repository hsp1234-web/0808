# src/main.py
import asyncio
import logging
import os
import sys
import uuid

# 繁體中文註解：為了能從根目錄直接執行此腳本，需要將專案根目錄加入到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict

# 繁體中文註解：設定日誌記錄器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 繁體中文註解：初始化 FastAPI 應用
app = FastAPI()

# 繁體中文註解：從 POC 模組中導入核心功能
from src.poc_tasks import db_poc

@app.on_event("startup")
async def startup_event():
    """
    在應用程式啟動時執行的事件。
    主要用於初始化資料庫和建立必要的目錄。
    """
    print("應用程式啟動中...")

    # 1. 初始化資料庫
    db_poc.initialize_database()

    # 2. 建立檔案儲存目錄
    os.makedirs("uploads_poc/tmp", exist_ok=True)
    os.makedirs("uploads_poc/files", exist_ok=True)
    os.makedirs("uploads_poc/reports", exist_ok=True)
    print("所有必要的目錄已確認或建立。")

    print("應用程式啟動完成。")

# 繁體中文註解：掛載靜態檔案目錄，這樣我們就可以提供 HTML, CSS, JS 檔案
# 我們使用 aiofiles 來異步提供檔案，但 FastAPI 的 StaticFiles 內部處理了這些細節
app.mount("/static", StaticFiles(directory="src/static"), name="static")

class ConnectionManager:
    """
    管理 WebSocket 連線的類別
    """
    def __init__(self):
        # 繁體中文註解：使用字典來儲存活躍的連線，鍵為 client_id
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """
        接受一個新的 WebSocket 連線
        """
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logging.info(f"新的 WebSocket 連線已建立：{client_id}")

    def disconnect(self, client_id: str):
        """
        中斷一個 WebSocket 連線
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logging.info(f"WebSocket 連線已中斷：{client_id}")

    async def send_personal_message(self, message: str, client_id: str):
        """
        向特定的客戶端發送訊息
        """
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        """
        向所有連接的客戶端廣播訊息
        """
        for connection in self.active_connections.values():
            await connection.send_text(message)

# 繁體中文註解：建立一個全域的連線管理器實例
manager = ConnectionManager()


@app.get("/health")
async def health_check():
    """
    提供給 Playwright 使用的簡單健康檢查端點。
    """
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    提供主頁面 (index.html)
    """
    # 繁體中文註解：這是一個臨時的根路由，之後會根據 MPA 的結構進行調整
    # 暫時指向 poc_test.html，方便快速測試
    with open("src/static/mpa/poc_test.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket 通訊的端點
    """
    await manager.connect(websocket, client_id)
    try:
        while True:
            # 繁體中文註解：保持連線開啟以接收訊息，但在這個實作中，我們主要用它來推送更新
            # 我們可以讓客戶端發送 ping 訊息來保持連線活躍
            data = await websocket.receive_text()
            logging.info(f"從 {client_id} 收到訊息: {data}")
            # 可以在這裡添加對收到的訊息的處理邏輯
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logging.info(f"客戶端 {client_id} 已斷開連線")


# 繁體中文註解：從 POC 模組中導入核心功能
from src.poc_tasks import db_poc, youtube_poc, transcriber_poc, gemini_poc
from src.poc_tasks.logging_poc import TIMEZONE
from datetime import datetime
import json

def run_in_background(coro):
    """
    一個輔助函數，用於在背景任務（通常是同步的）中安全地執行異步操作。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'get_running_loop' a RuntimeError if there is no running loop
        loop = None

    if loop and loop.is_running():
        # 如果事件循環正在運行，我們可以使用 run_coroutine_threadsafe
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        # 否則，我們啟動一個新的事件循環
        return asyncio.run(coro)

def send_status_update(client_id: str, status: str, message: str, data: dict = None):
    """
    一個輔助函數，用於格式化並發送 WebSocket 狀態更新。
    """
    update_message = {
        "status": status,
        "message": message,
        "data": data or {}
    }
    run_in_background(manager.send_personal_message(json.dumps(update_message), client_id))
    logging.info(f"[{client_id}] 發送狀態更新: {status} - {message}")

def process_youtube_task(task_id: str, url: str, api_key: str, client_id: str):
    """
    一個完整的背景任務函數，用於處理 YouTube 影片的下載、轉錄和分析。
    """
    logging.info(f"========== [{task_id}] 新任務開始 ==========")
    send_status_update(client_id, "processing", f"任務已接收: {task_id}")

    try:
        # 1. 在資料庫中建立任務
        now = datetime.now(TIMEZONE).isoformat()
        db_poc.create_task(task_id, url, now)
        send_status_update(client_id, "processing", "已在資料庫中建立任務記錄。")

        # 2. 下載 YouTube 影片
        send_status_update(client_id, "downloading", "正在下載 YouTube 影片...")
        audio_file_path = youtube_poc.process_youtube_video(task_id, url)
        if not audio_file_path:
            # 失敗訊息已在 youtube_poc 內部處理並記錄到資料庫
            send_status_update(client_id, "failed", "任務失敗於：影片下載階段。")
            logging.error(f"[{task_id}] 任務失敗於：影片下載階段。")
            return

        send_status_update(client_id, "download_completed", f"影片下載完成，音訊檔案位於: {audio_file_path}")

        # 3. 轉錄音訊檔案
        send_status_update(client_id, "transcribing", "正在轉錄音訊檔案...")
        transcript = transcriber_poc.transcribe_audio(task_id, audio_file_path)

        # 下載的檔案是 POC 的中間產物，轉錄完成後即可清理
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            logging.info(f"[{task_id}] 已清理臨時音訊檔案: {audio_file_path}")

        if not transcript:
            send_status_update(client_id, "failed", "任務失敗於：音訊轉錄階段。")
            logging.error(f"[{task_id}] 任務失敗於：音訊轉錄階段。")
            return

        send_status_update(client_id, "transcription_completed", "音訊轉錄完成。")

        # 4. 使用 Gemini 進行分析
        send_status_update(client_id, "analyzing", "正在使用 Gemini 進行分析...")
        report_path = gemini_poc.analyze_text(task_id, transcript, api_key)
        if not report_path:
            send_status_update(client_id, "failed", "任務失敗於：Gemini 分析階段。")
            logging.error(f"[{task_id}] 任務失敗於：Gemini 分析階段。")
            return

        send_status_update(client_id, "analysis_completed", f"Gemini 分析完成，報告位於: {report_path}")

        # 5. 任務成功
        send_status_update(client_id, "completed", "任務成功完成！", data={"report_path": report_path})
        logging.info(f"========== [{task_id}] 任務成功結束 ==========")

    except Exception as e:
        error_msg = f"處理過程中發生未預期的錯誤: {e}"
        logging.error(f"[{task_id}] {error_msg}", exc_info=True)
        finished_at = datetime.now(TIMEZONE).isoformat()
        db_poc.mark_task_as_failed(task_id, error_msg, finished_at)
        send_status_update(client_id, "failed", f"任務因未預期錯誤而失敗: {e}")


@app.post("/api/submit_task")
async def submit_task(request: Request, background_tasks: BackgroundTasks):
    """
    接收任務提交的 API 端點
    """
    payload = await request.json()
    url = payload.get("url")
    api_key = payload.get("api_key")
    client_id = payload.get("client_id", str(uuid.uuid4()))

    if not url or not api_key:
        return {"error": "缺少 'url' 或 'api_key'"}

    task_id = f"task-{uuid.uuid4()}"
    logging.info(f"收到來自 {client_id} 的任務請求: {payload}")

    # 繁體中文註解：將耗時的任務添加到背景任務中
    background_tasks.add_task(process_youtube_task, task_id, url, api_key, client_id)

    # 繁體中文註解：立即返回，告知前端任務已接收
    return {"message": "任務已成功接收並開始處理", "client_id": client_id, "task_id": task_id}

# 繁體中文註解：為了方便直接運行此檔案進行測試
if __name__ == "__main__":
    import uvicorn
    PORT = 8000
    logging.info(f"啟動開發伺服器於 http://127.0.0.1:{PORT}")
    # 繁體中文註解：使用 uvicorn 來運行 FastAPI 應用
    # 移除 reload=True 來避免檔案快取問題，確保執行的是最新的程式碼
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
