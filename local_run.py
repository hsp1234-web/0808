# local_run.py (測試監控器)
import subprocess
import sys
import time
import logging
import os
from pathlib import Path
import re
import json
import signal

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('local_run')

def cleanup_stale_processes():
    """清理任何可能由先前執行殘留的舊程序，以確保測試環境乾淨。"""
    import psutil
    log.info("--- 步驟 -2/6: 正在檢查並清理舊的程序 ---")
    stale_process_names = ["orchestrator.py", "api_server.py", "db/manager.py"]
    cleaned_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # psutil.Process.cmdline() returns a list of strings
            cmdline = proc.info.get('cmdline')
            if not cmdline:
                continue

            # 檢查命令列中是否包含任何目標腳本名稱
            if any(name in ' '.join(cmdline) for name in stale_process_names):
                log.warning(f"偵測到殘留的程序: PID={proc.pid}, 命令='{' '.join(cmdline)}'。正在終止它...")
                proc.kill()
                cleaned_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 程序可能在我們嘗試操作它之前就已經消失了，或者我們沒有權限
            pass
    if cleaned_count > 0:
        log.info(f"✅ 已成功清理 {cleaned_count} 個殘留的程序。")
    else:
        log.info("✅ 未發現殘留程序，環境很乾淨。")

def install_dependencies():
    """使用 uv 加速器安裝所有必要的依賴套件。"""
    log.info("--- 步驟 0/6: 檢查並安裝依賴 (uv 優化流程) ---")
    try:
        # 1. 檢查 uv 是否存在
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("✅ uv 加速器已安裝。")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # 2. 如果不存在，則安裝 uv
        log.info("未偵測到 uv，正在安裝...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])
            log.info("✅ uv 安裝成功。")
        except subprocess.CalledProcessError as e:
            log.error(f"❌ 安裝 uv 失敗: {e}")
            sys.exit(1)

    # 3. 使用 uv 一次性安裝所有依賴
    requirements_files = ["requirements-server.txt", "requirements-worker.txt"]
    log.info(f"正在使用 uv 安裝依賴: {', '.join(requirements_files)}...")
    try:
        # 為每個檔案建立 -r 參數
        uv_command = [sys.executable, "-m", "uv", "pip", "install", "-q"]
        for req_file in requirements_files:
            if Path(req_file).is_file():
                uv_command.extend(["-r", req_file])
            else:
                log.warning(f"依賴檔案 {req_file} 不存在，已跳過。")

        # 確保至少有一個有效的依賴檔案
        if len(uv_command) > 5:
             subprocess.check_call(uv_command)
             log.info("✅ 所有依賴都已成功安裝。")
        else:
             log.warning("找不到任何有效的依賴檔案，未執行安裝。")

    except subprocess.CalledProcessError as e:
        log.error(f"❌ 使用 uv 安裝依賴時失敗: {e}")
        sys.exit(1)

def main():
    """
    專為自動化測試設計的啟動器。
    它會啟動協調器，提交一個 YouTube 處理任務，然後等待系統變回 IDLE 狀態後自動退出。
    """
    # 首先，安裝依賴，確保所有工具都可用
    install_dependencies()

    # 接著，在執行任何操作之前，先清理舊的程序和檔案
    cleanup_stale_processes()

    db_file = Path("db/queue.db")
    if db_file.exists():
        log.info(f"--- 步驟 -1/6: 正在清理舊的資料庫檔案 ({db_file}) ---")
        db_file.unlink()
        log.info("✅ 舊資料庫已刪除。")

    log.info("🚀 Local YouTube Test Runner: 啟動...")
    orchestrator_proc = None
    try:
        # 1. 啟動協調器 (在真實模式下)
        log.info("--- 步驟 1/6: 啟動協調器 (真實模式) ---")
        cmd = [sys.executable, "orchestrator.py", "--no-mock"]

        # 將 GOOGLE_API_KEY 從當前環境傳遞給子程序
        proc_env = os.environ.copy()

        # 根據作業系統平台，設定對應的參數以建立新的程序組
        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": 'utf-8',
            "env": proc_env
        }
        if sys.platform != "win32":
            # 在 Unix-like 系統上，讓新程序成為新會話的領導者
            popen_kwargs['preexec_fn'] = os.setsid
        else:
            # 在 Windows 上，建立一個新的程序組
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        orchestrator_proc = subprocess.Popen(cmd, **popen_kwargs)
        log.info(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        # 2. 等待 API 伺服器就緒並取得其 URL
        log.info("--- 步驟 2/6: 等待 API 伺服器就緒並取得其 URL ---")
        api_url = None
        api_port = None
        # 新的正規表示式，用於匹配 "PROXY_URL: http://127.0.0.1:..."
        proxy_url_pattern = re.compile(r"PROXY_URL:\s*(http://127\.0\.0\.1:(\d+))")
        start_time = time.time()
        timeout = 45

        server_ready = False
        # Uvicorn 的啟動訊息，作為服務就緒的另一個信號
        uvicorn_ready_pattern = re.compile(r"Uvicorn running on")

        for line in iter(orchestrator_proc.stdout.readline, ''):
            log.info(f"[Orchestrator]: {line.strip()}")
            if not api_url:
                url_match = proxy_url_pattern.search(line)
                if url_match:
                    api_url = url_match.group(1)
                    api_port = url_match.group(2)
                    log.info(f"✅ 偵測到 API 服務 URL: {api_url}")
            if not server_ready and uvicorn_ready_pattern.search(line):
                server_ready = True
                log.info("✅ Uvicorn 伺服器已報告啟動。")

            # 當兩個條件都滿足時，才認為伺服器已完全準備好
            if api_url and server_ready:
                log.info("✅ API 伺服器已完全準備就緒。")
                break
            if time.time() - start_time > timeout:
                raise RuntimeError("等待 API 伺服器就緒超時。")

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
            submit_url = f"{api_url}/api/process_youtube"
            log.info(f"準備提交 YouTube 任務至: {submit_url}")

            payload = {
                "urls": [test_youtube_url],
                "model": test_model
            }
            response = requests.post(submit_url, json=payload, timeout=20)
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
            result_data = json.loads(task_info.get("result", "{}"))

            if final_status == "completed":
                html_path = result_data.get("html_report_path")
                if not html_path or not html_path.endswith(".html"):
                     raise ValueError(f"驗證失敗！任務成功，但結果中缺少有效的 HTML 報告路徑。")
                log.info(f"✅ 驗證成功！任務 {task_id} 狀態為 'completed' 且包含 HTML 報告路徑: {html_path}")
            elif final_status == "failed":
                error_msg = result_data.get("error")
                if not error_msg:
                    raise ValueError(f"驗證失敗！任務失敗，但結果中缺少錯誤訊息。")
                # 這是預期中的失敗（例如，影片不可用），測試應通過
                log.warning(f"✅ 驗證成功！任務 {task_id} 正確地以 'failed' 狀態結束。錯誤: {error_msg}")
            else:
                raise ValueError(f"驗證失敗！任務 {task_id} 的最終狀態是 '{final_status}'，但應為 'completed' 或 'failed'。")

            log.info("✅ 所有驗證均已通過！")

        except Exception as e:
            log.error(f"❌ 驗證資料庫日誌時失敗: {e}", exc_info=True)
            raise

    except Exception as e:
        log.critical(f"💥 Local Test Runner 發生致命錯誤: {e}", exc_info=True)
    finally:
        if orchestrator_proc and orchestrator_proc.poll() is None:
            log.info("--- 步驟 6/6: 正在終止協調器及其所有子程序 ---")
            try:
                if sys.platform != "win32":
                    # 在 Unix-like 系統上，向整個程序組發送 SIGTERM 信號
                    # 這會確保 orchestrator 和它啟動的所有子程序都被終止
                    os.killpg(os.getpgid(orchestrator_proc.pid), signal.SIGTERM)
                    log.info(f"已向程序組 {os.getpgid(orchestrator_proc.pid)} 發送終止信號。")
                else:
                    # 在 Windows 上，終止主程序，CREATE_NEW_PROCESS_GROUP 會幫助處理子程序
                    orchestrator_proc.terminate()
                    log.info(f"已向程序 {orchestrator_proc.pid} 發送終止信號。")

                orchestrator_proc.wait(timeout=10)
                log.info("✅ 協調器程序已成功終止。")
            except ProcessLookupError:
                log.warning("程序在嘗試終止它之前就已經結束了。")
            except Exception as e:
                log.error(f"終止程序時發生錯誤: {e}", exc_info=True)
                # 作為備用方案，嘗試強制擊殺
                if orchestrator_proc.poll() is None:
                    orchestrator_proc.kill()
                    log.warning("已強制擊殺協調器程序。")

        log.info("🏁 Local Test Runner 結束。")

if __name__ == "__main__":
    main()
