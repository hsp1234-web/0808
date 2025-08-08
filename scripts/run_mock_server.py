# scripts/run_mock_server.py
# This is a dedicated script for mock testing.
# It sets the environment variable *before* any other imports to guarantee mock mode.
import os
os.environ['MOCK_TRANSCRIBER'] = 'true'

import uvicorn
import sys
import threading
import time
import logging
import argparse
import subprocess
import socket

# --- 配置日誌系統 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger('mock_launch')

# --- 設定 sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 現在可以安全地匯入 ---
# 由於環境變數已設定，這些匯入將會使用模擬版本
from app.state import get_worker_state
from app.worker import run_worker

def wait_for_server_ready(port: int, timeout: int = 15) -> bool:
    log.info(f"正在等待模擬伺服器在埠號 {port} 上就緒...")
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                log.info("✅ 模擬伺服器已就緒！")
                return True
        except (socket.timeout, ConnectionRefusedError):
            time.sleep(0.5)
    log.error(f"❌ 等待模擬伺服器就緒超時 ({timeout}秒)。")
    return False

def monitor_worker_thread():
    monitor_log = logging.getLogger('monitor')
    monitor_log.info("智慧監控已啟動...")
    IDLE_TIMEOUT_SECONDS = 5
    BUSY_TIMEOUT_SECONDS = 60
    STARTING_TIMEOUT_SECONDS = 10
    time.sleep(3)
    while True:
        try:
            current_state = get_worker_state()
            status = current_state.get("worker_status", "unknown")
            last_heartbeat = current_state.get("last_heartbeat", 0)
            now = time.time()
            heartbeat_age = now - last_heartbeat
            timeout_limit = None
            is_timeout = False
            if status == 'starting':
                timeout_limit = STARTING_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit: is_timeout = True
            elif status == 'idle':
                timeout_limit = IDLE_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit: is_timeout = True
            elif status == 'busy':
                timeout_limit = BUSY_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit: is_timeout = True
            if int(now) % 5 == 0:
                 monitor_log.info(f"狀態: {status.upper():<8} | 心跳: {heartbeat_age:.1f}s 前 (超時: {str(timeout_limit)+'s' if timeout_limit else 'N/A'})")
            if is_timeout:
                monitor_log.critical(f"看門狗超時！工作者在 '{status}' 狀態下已卡住超過 {timeout_limit} 秒！")
                monitor_log.critical("正在強制終止整個應用程式...")
                os._exit(1)
            time.sleep(1)
        except Exception as e:
            monitor_log.error(f"監控執行緒發生未預期錯誤: {e}", exc_info=True)
            time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="以「模擬模式」啟動伺服器，用於測試。")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn 伺服器要監聽的埠號。")
    args = parser.parse_args()

    # --- 自我依賴安裝 ---
    log.info("--- [1/3] 正在檢查並安裝依賴 (模擬模式) ---")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-worker.txt"], check=True)
        log.info("✅ 依賴安裝完成。")
    except Exception as e:
        log.critical(f"❌ 依賴安裝失敗。錯誤: {e}")
        sys.exit(1)

    log.info("--- [2/3] 正在啟動核心服務 (模擬模式)...")

    worker_thread = threading.Thread(target=run_worker, name="WorkerThread", daemon=True)
    worker_thread.start()
    log.info("背景工作者 (Worker) 執行緒已啟動。")

    monitor_thread = threading.Thread(target=monitor_worker_thread, name="MonitorThread", daemon=True)
    monitor_thread.start()
    log.info("智慧監控 (Watchdog) 執行緒已啟動。")

    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": "app.main:app", "host": "0.0.0.0", "port": args.port, "log_level": "info"},
        daemon=True,
        name="UvicornThread"
    )
    server_thread.start()
    log.info(f"Uvicorn 伺服器執行緒已啟動，準備在埠號 {args.port} 上監聽。")

    if not wait_for_server_ready(args.port):
        log.critical("無法啟動模擬伺服器，正在終止應用程式。")
        sys.exit(1)

    log.info("--- [2/2] 模擬伺服器已啟動 ---")
    print("PHOENIX_MOCK_SERVER_READY", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n收到使用者中斷信號 (Ctrl+C)... 正在關閉模擬伺服器。")
    finally:
        log.info("模擬伺服器已關閉。")

if __name__ == "__main__":
    log_file_path = os.path.join(project_root, "mock_server_error.log")
    try:
        main()
    except Exception as e:
        # If any unhandled exception occurs, log it to a file
        with open(log_file_path, "w") as f:
            import traceback
            f.write(f"Unhandled exception in mock_server: {e}\n")
            f.write(traceback.format_exc())
        # Also log to the main logger if it's available
        try:
            log.critical(f"Unhandled exception caught at top level: {e}", exc_info=True)
        except NameError:
            pass # Logger might not be initialized
        sys.exit(1) # Ensure we exit with an error code
