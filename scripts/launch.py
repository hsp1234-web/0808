# scripts/local_run.py
import uvicorn
import os
import sys
import threading
import time
import logging
import argparse
import subprocess
import socket

# --- 配置日誌系統 ---
# 設定日誌記錄器，確保我們的日誌能和 Uvicorn 的日誌一起穩定輸出。
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] %(message)s',
    stream=sys.stdout,
)
# 為我們的腳本建立一個專用的 logger
log = logging.getLogger('launch')


# --- 設定 sys.path ---
# 確保專案根目錄在 Python 的搜尋路徑中，以便能正確匯入 app 模組
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 現在可以安全地匯入 ---
from app.state import get_worker_state
from app.worker import run_worker

def wait_for_server_ready(port: int, timeout: int = 15) -> bool:
    """等待 Uvicorn 伺服器就緒，直到可以建立連線。"""
    log.info(f"正在等待伺服器在埠號 {port} 上就緒...")
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                log.info("✅ 伺服器已就緒！")
                return True
        except (socket.timeout, ConnectionRefusedError):
            time.sleep(0.5)
    log.error(f"❌ 等待伺服器就緒超時 ({timeout}秒)。")
    return False

def monitor_worker_thread():
    """
    這是在背景執行緒中運行的智慧監控迴圈（看門狗）。
    它會持續監控背景工作者的狀態，並在偵測到問題時強制終止整個應用程式。
    """
    monitor_log = logging.getLogger('monitor')
    monitor_log.info("智慧監控已啟動...")

    # --- 超時設定 ---
    IDLE_TIMEOUT_SECONDS = 5
    BUSY_TIMEOUT_SECONDS = 60
    STARTING_TIMEOUT_SECONDS = 10

    # 給予工作者執行緒一點啟動和初始化的時間
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
                if heartbeat_age > timeout_limit:
                    is_timeout = True
            elif status == 'idle':
                timeout_limit = IDLE_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit:
                    is_timeout = True
            elif status == 'busy':
                timeout_limit = BUSY_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit:
                    is_timeout = True

            # 每 5 秒記錄一次狀態，以避免日誌過於嘈雜
            if int(now) % 5 == 0:
                 monitor_log.info(f"狀態: {status.upper():<8} | 心跳: {heartbeat_age:.1f}s 前 (超時: {str(timeout_limit)+'s' if timeout_limit else 'N/A'})")

            if is_timeout:
                monitor_log.critical(f"看門狗超時！工作者在 '{status}' 狀態下已卡住超過 {timeout_limit} 秒！")
                monitor_log.critical("正在強制終止整個應用程式...")
                # 在執行緒中，os._exit 是最可靠的強制退出方式，它會立即終止整個進程。
                os._exit(1)

            time.sleep(1)
        except Exception as e:
            monitor_log.error(f"監控執行緒發生未預期錯誤: {e}", exc_info=True)
            time.sleep(5) # 避免錯誤快速循環

def main():
    """
    應用程式主入口。
    採用「單一進程，多執行緒」架構，穩定地啟動所有服務。
    可以選擇性地執行端對端測試。
    """
    parser = argparse.ArgumentParser(description="啟動核心服務、Uvicorn 伺服器並可選擇性執行測試。")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn 伺服器要監聽的埠號。")
    parser.add_argument("--run-test", action="store_true", help="啟動後執行端對端測試。")
    parser.add_argument("--exit-after-test", action="store_true", help="測試完成後自動關閉伺服器 (僅在 --run-test 啟用時有效)。")
    args = parser.parse_args()

    log.info("==================================================")
    log.info("🚀 正在啟動核心服務 (單進程，多執行緒模式)...")
    log.info("==================================================")

    # 1. 啟動背景工作者執行緒
    worker_thread = threading.Thread(target=run_worker, name="WorkerThread", daemon=True)
    worker_thread.start()
    log.info("背景工作者 (Worker) 執行緒已啟動。")

    # 2. 啟動智慧監控（看門狗）執行緒
    monitor_thread = threading.Thread(target=monitor_worker_thread, name="MonitorThread", daemon=True)
    monitor_thread.start()
    log.info("智慧監控 (Watchdog) 執行緒已啟動。")

    # 3. 在背景執行緒中啟動 Uvicorn 伺服器
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": "app.main:app", "host": "0.0.0.0", "port": args.port, "log_level": "info"},
        daemon=True,
        name="UvicornThread"
    )
    server_thread.start()
    log.info(f"Uvicorn 伺服器執行緒已啟動，準備在埠號 {args.port} 上監聽。")

    # 4. 等待伺服器就緒
    if not wait_for_server_ready(args.port):
        log.critical("無法啟動伺服器，正在終止應用程式。")
        sys.exit(1)

    # 5. 如果使用者指定，則執行端對端測試
    if args.run_test:
        log.info("--- [開始執行端對端測試] ---")
        test_script_path = os.path.join(project_root, "scripts", "run_e2e_test.py")
        result = subprocess.run(
            [sys.executable, test_script_path, "--port", str(args.port)],
            capture_output=True, text=True, encoding='utf-8'
        )

        # 將測試腳本的輸出直接打印到主控台
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            log.info("--- [端對端測試成功通過] ---")
            if args.exit_after_test:
                log.info("測試成功，根據 --exit-after-test 選項，應用程式將在 3 秒後關閉。")
                time.sleep(3)
                sys.exit(0)
        else:
            log.critical("--- [端對端測試失敗] ---")
            if args.exit_after_test:
                log.error("測試失敗，根據 --exit-after-test 選項，應用程式將在 3 秒後關閉。")
                time.sleep(3)
                sys.exit(1)

    # 6. 如果沒有自動退出，則保持主執行緒存活，等待使用者中斷
    log.info("✅ 所有服務已啟動。應用程式正在運行...")
    log.info("使用 Ctrl+C 來停止所有服務。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n收到使用者中斷信號 (Ctrl+C)... 正在關閉應用程式。")
    finally:
        log.info("應用程式已關閉。再見！")
        # 由於所有背景執行緒都是 daemon，它們會隨主執行緒的退出而自動終止。

if __name__ == "__main__":
    main()
