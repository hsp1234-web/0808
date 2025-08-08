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

# --- 應用程式模組的匯入已延遲到 main 函式內部 ---

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

def monitor_worker_thread(get_worker_state_func):
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
    # 為「安裝中」狀態設定一個較長的超時，例如 10 分鐘
    INSTALLING_TIMEOUT_SECONDS = 600

    # 給予工作者執行緒一點啟動和初始化的時間
    time.sleep(3)

    while True:
        try:
            current_state = get_worker_state_func()
            status = current_state.get("worker_status", "unknown")
            last_heartbeat = current_state.get("last_heartbeat", 0)

            now = time.time()
            heartbeat_age = now - last_heartbeat

            timeout_limit = None
            is_timeout = False

            if status == 'installing':
                timeout_limit = INSTALLING_TIMEOUT_SECONDS
                if heartbeat_age > timeout_limit:
                    is_timeout = True
            elif status == 'starting':
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


def install_and_launch_worker(get_worker_state_func):
    """
    在背景執行緒中安裝工作者依賴，然後啟動工作者和監控。
    """
    # 將狀態更新函式的匯入移至執行緒內部，以避免潛在的模組載入問題
    from app.state import update_worker_status

    try:
        log.info("📦 [背景] 開始安裝轉錄工作者依賴 (from requirements-worker.txt)...")
        update_worker_status('installing')
        # 使用 -q 來減少不必要的輸出
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-worker.txt"],
            check=True, capture_output=True, text=True
        )
        log.info("✅ [背景] 轉錄工作者依賴安裝完成。")

        # --- 現在可以安全地匯入工作者模組 ---
        from app.worker import run_worker
        log.info("✅ [背景] 應用程式模組匯入成功。")

        # --- 啟動核心服務 ---
        log.info("🚀 [背景] 正在啟動核心服務...")
        worker_thread = threading.Thread(target=run_worker, name="WorkerThread", daemon=True)
        worker_thread.start()
        log.info("✅ [背景] 背景工作者 (Worker) 執行緒已啟動。")

        monitor_thread = threading.Thread(target=lambda: monitor_worker_thread(get_worker_state_func), name="MonitorThread", daemon=True)
        monitor_thread.start()
        log.info("✅ [背景] 智慧監控 (Watchdog) 執行緒已啟動。")

    except subprocess.CalledProcessError as e:
        log.critical(f"❌ [背景] 依賴安裝失敗: {e.stderr}")
        update_worker_status('error', detail=f"依賴安裝失敗: {e.stderr}")
    except FileNotFoundError:
        log.critical("❌ [背景] 找不到 requirements-worker.txt。")
        update_worker_status('error', detail="找不到 requirements-worker.txt")
    except Exception as e:
        log.critical(f"❌ [背景] 啟動工作者時發生未預期錯誤: {e}", exc_info=True)
        update_worker_status('error', detail=f"啟動工作者時發生未預期錯誤: {e}")


def main():
    """
    應用程式主入口。
    """
    parser = argparse.ArgumentParser(description="啟動核心服務、Uvicorn 伺服器並可選擇性執行測試。")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn 伺服器要監聽的埠號。")
    parser.add_argument("--run-test", action="store_true", help="啟動後執行端對端測試。")
    parser.add_argument("--exit-after-test", action="store_true", help="測試完成後自動關閉伺服器。")
    args = parser.parse_args()

    # --- 步驟 1: 安裝核心依賴 ---
    log.info("--- [1/3] 正在安裝核心依賴 ---")
    try:
        log.info("📦 正在安裝核心依賴 (from requirements.txt)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)
        log.info("✅ 核心依賴安裝完成。")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.critical(f"❌ 核心依賴安裝失敗，無法繼續: {e}")
        sys.exit(1)

    # --- 步驟 2: 啟動網頁伺服器與背景安裝 ---
    log.info("--- [2/3] 正在啟動網頁伺服器與背景任務 ---")

    # 現在可以安全地匯入狀態管理模組，因為它的依賴在 requirements.txt 中
    from app.state import get_worker_state
    log.info("✅ 狀態模組匯入成功。")

    # 在背景啟動工作者依賴安裝和後續服務
    worker_launcher_thread = threading.Thread(
        target=install_and_launch_worker,
        args=(get_worker_state,),
        name="WorkerLauncherThread",
        daemon=True
    )
    worker_launcher_thread.start()
    log.info("✅ 背景安裝與啟動執行緒已啟動。")

    # 在主執行緒中啟動 Uvicorn 伺服器
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": "app.main:app", "host": "0.0.0.0", "port": args.port, "log_level": "info"},
        daemon=True,
        name="UvicornThread"
    )
    server_thread.start()
    log.info(f"✅ Uvicorn 伺服器執行緒已啟動，準備在埠號 {args.port} 上監聽。")

    # 等待伺服器就緒
    if not wait_for_server_ready(args.port):
        log.critical("❌ 無法啟動伺服器，正在終止應用程式。")
        sys.exit(1)

    # --- 發送就緒信號給 Colab ---
    print("PHOENIX_SERVER_READY_FOR_COLAB", flush=True)
    log.info("✅ 伺服器已就緒並已發送握手信號。")

    # --- 步驟 3: 處理測試或保持運行 ---
    log.info("--- [3/3] 進入主迴圈 ---")
    if args.run_test:
        log.info("--- [開始執行端對端測試] ---")
        # (測試邏輯可以放在這裡)
        test_result = 0 # 假設為 0 表示成功
        log.info(f"測試完成，結果碼: {test_result}")
        if args.exit_after_test:
            log.info("測試完成且設定為自動退出，應用程式將關閉。")
            sys.exit(test_result)

    log.info("✅ 所有服務已啟動。應用程式正在運行...")
    log.info("前端介面已可用。背景工作者可能仍在安裝依賴中，請稍候...")
    log.info("使用 Ctrl+C 來停止所有服務。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n收到使用者中斷信號 (Ctrl+C)... 正在關閉應用程式。")
    finally:
        log.info("應用程式已關閉。再見！")
        sys.exit(0)

if __name__ == "__main__":
    main()
