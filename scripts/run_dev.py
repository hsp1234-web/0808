# scripts/run_dev.py
import uvicorn
import os
import sys
import threading
import socket
import multiprocessing
import time

# --- 設定 sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 現在可以安全地匯入 ---
from app.worker import run_worker
from app.state import get_worker_status

def find_available_port():
    """動態尋找一個未被佔用的 TCP 埠號。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_server(host: str, port: int):
    """
    Uvicorn 伺服器的進入點函式，將在一個獨立的進程中執行。
    """
    print(f"🚀 [Server Process] Uvicorn 伺服器正在 http://{host}:{port} 上啟動...")
    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("🛑 [Server Process] 收到退出信號，正在關閉伺服器。")
    except Exception as e:
        print(f"💥 [Server Process] 伺服器發生未預期錯誤: {e}")
    finally:
        print("✅ [Server Process] 伺服器已關閉。")


def start_with_smart_monitoring():
    """
    啟動完整的開發環境，包含智慧監控機制來監控背景工作者的健康狀態。
    """
    print("==================================================")
    print("🚀 正在啟動 鳳凰轉錄儀 (附帶智慧監控模式)...")
    print("==================================================")

    # 1. 啟動背景工作者執行緒
    # daemon=True 確保主執行緒退出時，此執行緒也會被終止
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    print("✅ [Monitor] 背景工作者 (Worker) 已在獨立執行緒中啟動。")

    # 2. 動態尋找可用埠號並啟動伺服器
    host = "127.0.0.1"
    port = find_available_port()
    server_process = multiprocessing.Process(
        target=run_server,
        args=(host, port),
        daemon=True
    )
    server_process.start()
    print(f"✅ [Monitor] Uvicorn 伺服器進程已啟動 (PID: {server_process.pid})。")
    print(f"\n請在瀏覽器中開啟 http://{host}:{port} 來存取介面。")
    print("使用 Ctrl+C 來停止啟動器和所有服務。")

    # 3. 啟動智慧監控迴圈
    print("\n⏱️  [Monitor] 智慧監控已啟動，正在監控工作者心跳...")
    # 給予 worker 初始化的時間
    time.sleep(2)

    # 定義動態超時時間
    IDLE_TIMEOUT = 5  # 閒置時，5秒沒心跳就認為有問題
    BUSY_TIMEOUT = 60 # 忙碌時，給予 60 秒的寬限期來處理任務

    try:
        while True:
            # 檢查伺服器或工作者執行緒是否還活著
            if not server_process.is_alive():
                print("❌ [Monitor] 偵測到伺服器進程已意外終止。正在退出...")
                sys.exit(1)
            if not worker_thread.is_alive():
                print("❌ [Monitor] 偵測到工作者執行緒已意外終止。正在退出...")
                # 同樣需要關閉伺服器
                if server_process.is_alive():
                    server_process.terminate()
                    server_process.join(1)
                sys.exit(1)

            # 讀取 worker 的共享狀態
            status = get_worker_status()
            worker_status = status["worker_status"]
            last_heartbeat = status["last_heartbeat"]

            # 根據狀態決定超時時間
            timeout_seconds = IDLE_TIMEOUT if worker_status == 'IDLE' else BUSY_TIMEOUT

            # 檢查是否已超時
            if time.time() - last_heartbeat > timeout_seconds:
                print(f"🚨 [Monitor] 偵測到工作者無回應！")
                print(f"   - 目前狀態: {worker_status}")
                print(f"   - 上次心跳: {time.ctime(last_heartbeat)}")
                print(f"   - 超時設定: {timeout_seconds} 秒")
                print("💥 [Monitor] 正在強制終止所有服務...")

                # 執行關閉程序
                if server_process.is_alive():
                    server_process.terminate()
                    server_process.join(timeout=5)
                    if server_process.is_alive():
                        server_process.kill()
                print("🛑 [Monitor] 已終止服務。監控器正在退出。")
                sys.exit(1)

            # 每秒檢查一次
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 [Monitor] 收到使用者中斷信號 (Ctrl+C)。")
    finally:
        print("... 正在優雅地關閉所有服務...")
        if server_process.is_alive():
            print("... 正在關閉 Uvicorn 伺服器進程...")
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
        print("✅ 所有服務已成功關閉。再見！")
        sys.exit(0)


if __name__ == "__main__":
    # 在 Windows 和 macOS 上，multiprocessing 的預設啟動方法可能導致問題
    # 明確設定為 'fork' (如果系統支援) 或 'spawn' 可以提高穩定性
    if sys.platform != 'win32':
        multiprocessing.set_start_method("fork", force=True)
    else:
        # 在 Windows 上，'fork' 不可用，'spawn' 是預設且安全的選擇
        multiprocessing.set_start_method("spawn", force=True)
    start_with_smart_monitoring()
