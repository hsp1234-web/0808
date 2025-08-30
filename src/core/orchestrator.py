import time
import subprocess
import sys
import logging
import argparse
import threading
from pathlib import Path
import socket
import os

os.environ['TZ'] = 'Asia/Taipei'
if sys.platform != 'win32':
    time.tzset()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
from db.client import DBClient, get_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('orchestrator')

# Global variable to hold the listener
log_listener = None

def setup_database_logging():
    global log_listener
    try:
        from db.log_handler import DatabaseLogHandler
        from logging.handlers import QueueHandler, QueueListener
        import queue

        log_queue = queue.Queue(-1)
        db_handler = DatabaseLogHandler(source='orchestrator_db_writer')

        if log_listener is None:
            log_listener = QueueListener(log_queue, db_handler)
            log_listener.start()

        root_logger = logging.getLogger()

        for handler in root_logger.handlers[:]:
            if isinstance(handler, DatabaseLogHandler):
                root_logger.removeHandler(handler)

        if not any(isinstance(h, QueueHandler) for h in root_logger.handlers):
            queue_handler = QueueHandler(log_queue)
            root_logger.addHandler(queue_handler)
            log.info("✅ 非阻塞的資料庫日誌系統已設定完成。")

    except Exception as e:
        log.error(f"整合資料庫日誌時發生錯誤: {e}", exc_info=True)

def stop_database_logging():
    global log_listener
    if log_listener:
        log.info("⏳ 正在停止日誌監聽器...")
        log_listener.stop()
        log_listener = None

def stream_reader(stream, prefix, ready_event=None, ready_signal=None):
    for line in iter(stream.readline, ''):
        stripped_line = line.strip()
        log.info(f"[{prefix}] {stripped_line}")
        if ready_event and not ready_event.is_set() and ready_signal and ready_signal in stripped_line:
            ready_event.set()
            log.info(f"✅ 偵測到來自 '{prefix}' 的就緒信號 '{ready_signal}'！")
    stream.close()

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def main():
    parser = argparse.ArgumentParser(description="系統協調器。")
    parser.add_argument("--mock", action="store_true", help="如果設置，則 worker 將以模擬模式運行。")
    parser.add_argument("--port", type=int, default=None, help="指定 API 伺服器運行的固定埠號。")
    args = parser.parse_args()

    mode_string = "模擬 (Mock)" if args.mock else "真實 (Real)"
    log.info(f"🚀 協調器啟動。模式: {mode_string}")

    processes = []
    threads = []
    db_client = None

    try:
        # 1. 啟動資料庫管理器
        log.info("🔧 正在啟動資料庫管理者服務...")
        db_manager_cmd = [sys.executable, "src/db/manager.py"]
        db_manager_proc = subprocess.Popen(db_manager_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        processes.append(db_manager_proc)
        log.info(f"✅ 資料庫管理者子程序已建立，PID: {db_manager_proc.pid}")

        db_ready_event = threading.Event()
        db_stdout_thread = threading.Thread(target=stream_reader, args=(db_manager_proc.stdout, 'db_manager', db_ready_event, "DB_MANAGER_READY"))
        db_stdout_thread.daemon = True
        db_stdout_thread.start()
        threads.append(db_stdout_thread)

        log.info(f"正在等待資料庫管理者就緒 (超時: 30秒)...")
        if not db_ready_event.wait(timeout=30):
            raise RuntimeError("資料庫管理者服務啟動超時。")
        log.info("✅ 資料庫管理者服務已完全就緒。")

        # JULES'S FIX (2025-08-30): 加入一個微小的延遲，以解決競爭條件。
        # 即使 db_manager 已發出就緒信號，作業系統可能仍需極短時間來完全開啟監聽埠。
        # 沒有這個延遲，api_server 在啟動時的日誌系統可能會因為無法立即連線到 db_manager 而掛起。
        time.sleep(1)

        # 2. 資料庫就緒後，建立客戶端並設定日誌系統
        db_client = get_client()
        setup_database_logging()

        # 3. 啟動 API 伺服器
        log.info("🔧 正在啟動 API 伺服器...")
        api_port = args.port if args.port else find_free_port()
        api_server_cmd = [sys.executable, "src/api/api_server.py", "--port", str(api_port)]
        if args.mock:
            api_server_cmd.append("--mock")

        api_proc = subprocess.Popen(api_server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        processes.append(api_proc)
        log.info(f"✅ API 伺服器已啟動，PID: {api_proc.pid}，埠號: {api_port}")

        proxy_url = f"http://127.0.0.1:{api_port}"
        print(f"PROXY_URL: {proxy_url}", flush=True)
        log.info(f"已向外部監聽器報告代理 URL: {proxy_url}")

        api_stdout_thread = threading.Thread(target=stream_reader, args=(api_proc.stdout, 'api_server', None, None))
        api_stderr_thread = threading.Thread(target=stream_reader, args=(api_proc.stderr, 'api_server_stderr', None, None))
        threads.extend([api_stdout_thread, api_stderr_thread])
        for t in [api_stdout_thread, api_stderr_thread]:
            t.daemon = True
            t.start()

        log.info("🚫 [架構性決策] Worker 程序已被永久停用，以支援 WebSocket 驅動的新架構。")
        log.info("--- [協調器進入監控模式] ---")

        last_heartbeat_time = 0
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError(f"子程序 {proc.args} (PID: {proc.pid}) 已意外終止，返回碼: {proc.returncode}")

            # 4. 心跳檢查
            if time.time() - last_heartbeat_time > 5:
                try:
                    active_tasks = db_client.are_tasks_active()
                    log.info(f"HEARTBEAT: RUNNING {'(TASKS ACTIVE)' if active_tasks else ''}")
                    last_heartbeat_time = time.time()
                except Exception as e:
                    log.error(f"心跳檢查失敗: {e}", exc_info=True)

            time.sleep(1)

    except (KeyboardInterrupt, RuntimeError) as e:
        if isinstance(e, RuntimeError):
            log.error(f"協調器因錯誤而終止: {e}")
        else:
            log.info("\n🛑 收到中斷信號，正在優雅關閉所有服務...")
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                log.info(f"⏳ 正在終止子程序 (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    log.warning(f"⚠️ 子程序 {proc.pid} 未能正常終止，將強制擊殺。")
                    proc.kill()

        stop_database_logging()
        log.info("👋 協調器已關閉。")

if __name__ == "__main__":
    main()
