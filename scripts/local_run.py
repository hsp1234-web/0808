# scripts/local_run.py
import uvicorn
import os
import sys
import threading
import socket
import multiprocessing
import time
import requests

# --- 設定 sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 現在可以安全地匯入 ---
# 注意：由於我們現在使用 multiprocessing，工作者也必須在主進程的 __main__ 區塊中啟動
# 或者在 run_server 函式中啟動，以避免在子進程中被重新初始化。
# 我們將其保留在主進程中啟動。
from app.worker import run_worker

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
        # 在真實應用中，這裡應該有更詳細的日誌記錄
    finally:
        print("✅ [Server Process] 伺服器已關閉。")


def start_with_watchdog():
    """
    啟動完整的開發環境，包含看門狗機制來監控伺服器健康狀態。
    """
    print("==================================================")
    print("🚀 正在啟動 鳳凰轉錄儀 (附帶看門狗模式)...")
    print("==================================================")

    # 1. 啟動背景工作者執行緒
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    print("✅ [Watchdog] 背景工作者 (Worker) 已在獨立執行緒中啟動。")

    # 2. 動態尋找可用埠號
    host = "127.0.0.1"
    port = find_available_port()
    health_check_url = f"http://{host}:{port}/api/health"
    print(f"✅ [Watchdog] 動態尋找到可用埠號: {port}")
    print(f"✅ [Watchdog] 健康檢查端點: {health_check_url}")

    # 3. 在獨立進程中啟動 Uvicorn 伺服器
    server_process = multiprocessing.Process(
        target=run_server,
        args=(host, port),
        daemon=True # 設定為守護進程
    )
    server_process.start()
    print(f"✅ [Watchdog] Uvicorn 伺服器進程已啟動 (PID: {server_process.pid})。")
    print(f"\n請在瀏覽器中開啟 http://{host}:{port} 來存取介面。")
    print("使用 Ctrl+C 來停止啟動器和所有服務。")

    # 4. 啟動看門狗監控迴圈
    print("\n⏱️  [Watchdog] 看門狗已啟動，正在監控伺服器健康狀態...")
    time.sleep(5) # 給伺服器一點啟動時間

    consecutive_failures = 0
    max_failures = 3 # 連續失敗 3 次後觸發
    check_interval = 7 # 每 7 秒檢查一次 (3 * 7 = 21 秒，符合超時要求)

    try:
        while True:
            if not server_process.is_alive():
                print("❌ [Watchdog] 偵測到伺服器進程已意外終止。正在退出...")
                sys.exit(1)

            try:
                # 執行健康檢查，設定較短的超時
                response = requests.get(health_check_url, timeout=3)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    if consecutive_failures > 0:
                        print("✅ [Watchdog] 伺服器已恢復正常。")
                    consecutive_failures = 0
                else:
                    raise ValueError(f"健康檢查回傳異常狀態: {response.status_code}")

            except requests.exceptions.RequestException as e:
                consecutive_failures += 1
                print(f"⚠️ [Watchdog] 健康檢查失敗 (第 {consecutive_failures}/{max_failures} 次): {e}")

            if consecutive_failures >= max_failures:
                print(f"🚨 [Watchdog] 伺服器連續 {max_failures} 次無回應，已超過 20 秒超時限制！")
                print("💥 [Watchdog] 正在強制終止卡死的伺服器進程...")
                server_process.terminate() # 傳送 SIGTERM 信號
                server_process.join(timeout=5) # 等待進程結束
                if server_process.is_alive():
                    print("🔪 [Watchdog] 伺服器未能正常終止，將強制擊殺 (kill)。")
                    server_process.kill() # 傳送 SIGKILL 信號
                print("🛑 [Watchdog] 已終止伺服器。看門狗正在退出。")
                sys.exit(1)

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\n🛑 [Watchdog] 收到使用者中斷信號 (Ctrl+C)。")
    finally:
        print(" gracefully shutting down...")
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
    multiprocessing.set_start_method("fork", force=True) if sys.platform != 'win32' else multiprocessing.set_start_method("spawn", force=True)
    start_with_watchdog()
