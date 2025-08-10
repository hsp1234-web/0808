# local_run.py (測試監控器)
import subprocess
import sys
import time
import logging
import os
from pathlib import Path
import re
import json

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('local_run')

def install_dependencies():
    """安裝所有必要的依賴套件。"""
    log.info("--- 步驟 0/6: 檢查並安裝依賴 ---")
    requirements_files = ["requirements.txt", "requirements-worker.txt"]
    for req_file in requirements_files:
        log.info(f"正在安裝 {req_file}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", req_file])
            log.info(f"✅ {req_file} 中的依賴已成功安裝。")
        except subprocess.CalledProcessError as e:
            log.error(f"❌ 安裝 {req_file} 失敗: {e}")
            sys.exit(1)
    log.info("✅ 所有依賴都已安裝。")

def main():
    """
    專為自動化測試設計的啟動器。
    它會啟動協調器，提交一個 YouTube 處理任務，然後等待系統變回 IDLE 狀態後自動退出。
    """
    db_file = Path("db/queue.db")
    if db_file.exists():
        log.info(f"--- 步驟 -1/6: 正在清理舊的資料庫檔案 ({db_file}) ---")
        db_file.unlink()
        log.info("✅ 舊資料庫已刪除。")

    install_dependencies()

    log.info("🚀 Local YouTube Test Runner: 啟動...")
    orchestrator_proc = None
    try:
        # 1. 啟動協調器 (在真實模式下)
        log.info("--- 步驟 1/6: 啟動協調器 (真實模式) ---")
        cmd = [sys.executable, "orchestrator.py", "--no-mock"]

        # 將 GOOGLE_API_KEY 從當前環境傳遞給子程序
        proc_env = os.environ.copy()

        orchestrator_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            env=proc_env
        )
        log.info(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        # 2. 等待 API 伺服器就緒並取得埠號
        log.info("--- 步驟 2/6: 等待 API 伺服器就緒並取得埠號 ---")
        api_port = None
        port_pattern = re.compile(r"API_PORT:\s*(\d+)")
        start_time = time.time()
        timeout = 45

        server_ready = False
        uvicorn_ready_pattern = re.compile(r"Uvicorn running on")

        for line in iter(orchestrator_proc.stdout.readline, ''):
            log.info(f"[Orchestrator]: {line.strip()}")
            if not api_port:
                port_match = port_pattern.search(line)
                if port_match:
                    api_port = port_match.group(1)
                    log.info(f"✅ 偵測到 API 埠號: {api_port}")
            if not server_ready and uvicorn_ready_pattern.search(line):
                server_ready = True
                log.info("✅ Uvicorn 伺服器已就緒。")
            if api_port and server_ready:
                log.info("✅ API 伺服器已完全準備就緒。")
                break
            if time.time() - start_time > timeout:
                raise RuntimeError("API server did not become ready in time.")

        if orchestrator_proc.poll() is not None:
             raise RuntimeError("協調器在啟動過程中意外終止。")

        # 3. 提交並啟動一個 YouTube 測試任務
        log.info("--- 步驟 3/6: 提交並啟動一個 YouTube 測試任務 ---")
        task_id = None
        try:
            import requests
            import websocket

            # 使用一個簡短、穩定的影片進行測試 (例如，公有領域的有聲書)
            test_youtube_url = "https://www.youtube.com/watch?v=LdeC_0G0E1g" # The Wonderful Wizard of Oz, Chapter 1
            test_model = "models/gemini-1.5-flash-latest"

            # Part A: Submit task via HTTP POST
            api_url = f"http://127.0.0.1:{api_port}/api/process_youtube"
            log.info(f"準備提交 YouTube 任務至: {api_url}")

            payload = {
                "urls": [test_youtube_url],
                "model": test_model
            }
            response = requests.post(api_url, json=payload, timeout=20)
            response.raise_for_status()

            response_data = response.json()
            task_id = response_data["tasks"][0]["task_id"]
            log.info(f"✅ 已成功提交 YouTube 任務，將追蹤任務 ID: {task_id}")

            # Part B: Start task via WebSocket
            ws_url = f"ws://127.0.0.1:{api_port}/api/ws"
            log.info(f"準備透過 WebSocket ({ws_url}) 啟動任務...")
            ws = websocket.create_connection(ws_url, timeout=10)
            start_command = {
                "type": "START_YOUTUBE_PROCESSING",
                "payload": {"task_id": task_id}
            }
            ws.send(json.dumps(start_command))
            log.info(f"✅ 已發送啟動指令: {json.dumps(start_command)}")
            ws.close()

        except Exception as e:
            log.error(f"❌ 提交或啟動 YouTube 任務時失敗: {e}", exc_info=True)
            raise

        # 4. 監聽心跳信號，直到系統返回 IDLE
        log.info("--- 步驟 4/6: 監聽心跳，等待系統返回 IDLE ---")
        idle_detected = False
        # 增加超時時間，因為真實的 AI 處理需要時間
        timeout = time.time() + 300 # 5 分鐘超時

        for line in iter(orchestrator_proc.stdout.readline, ''):
            line = line.strip()
            log.info(f"[Orchestrator]: {line}")
            if "HEARTBEAT: IDLE" in line:
                log.info("✅ 偵測到 IDLE 狀態，任務週期結束。")
                idle_detected = True
                break
            if time.time() > timeout:
                log.error("❌ 測試超時！系統未在指定時間內返回 IDLE。")
                break

        if not idle_detected:
            raise RuntimeError("Test failed: Did not detect IDLE state after task submission.")

        # 5. 驗證任務最終狀態
        log.info("--- 步驟 5/6: 驗證任務最終狀態 ---")
        try:
            time.sleep(2) # 等待最後的資料庫寫入操作
            from db.client import get_client
            db_client = get_client()

            log.info(f"正在驗證任務 {task_id} 的最終狀態...")
            task_info = db_client.get_task_status(task_id)
            if not task_info:
                raise ValueError(f"驗證失敗：在資料庫中找不到任務 {task_id}。")

            final_status = task_info.get("status")
            if final_status != "completed":
                raise ValueError(f"驗證失敗！任務 {task_id} 的最終狀態是 '{final_status}'，但應為 'completed'。")

            result_data = json.loads(task_info.get("result", "{}"))
            html_path = result_data.get("html_report_path")
            if not html_path or not html_path.endswith(".html"):
                 raise ValueError(f"驗證失敗！任務 {task_id} 的結果中缺少有效的 HTML 報告路徑。")

            log.info(f"✅ 驗證成功！任務 {task_id} 狀態為 'completed' 且包含 HTML 報告路徑: {html_path}")
            log.info("✅ 所有驗證均已通過！")

        except Exception as e:
            log.error(f"❌ 驗證資料庫日誌時失敗: {e}", exc_info=True)
            raise

    except Exception as e:
        log.critical(f"💥 Local Test Runner 發生致命錯誤: {e}", exc_info=True)
    finally:
        if orchestrator_proc and orchestrator_proc.poll() is None:
            log.info("--- 步驟 6/6: 正在終止協調器 ---")
            orchestrator_proc.terminate()
            orchestrator_proc.wait(timeout=5)
        log.info("🏁 Local Test Runner 結束。")

if __name__ == "__main__":
    main()
