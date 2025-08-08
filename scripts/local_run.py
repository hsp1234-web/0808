# -*- coding: utf-8 -*-
import os
import sys
import threading
import socket
import multiprocessing
import time

# --- 設定 sys.path ---
# 確保專案根目錄在 Python 的搜尋路徑中，以便能正確匯入 app 模組
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- 應用程式模組的匯入將延遲到依賴安裝之後 ---

def find_available_port():
    """動態尋找一個未被佔用的 TCP 埠號。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_server(host: str, port: int, ready_signal: multiprocessing.Event):
    """
    Uvicorn 伺服器的進入點函式，將在一個獨立的進程中執行。
    """
    # 在新進程開始時，重新匯入 uvicorn 和應用程式
    import uvicorn
    from app.main import app

    # 設置一個事件回調，當 uvicorn 啟動完成時發出信號
    class UvicornServer(uvicorn.Server):
        def handle_exit(self, sig: int, frame) -> None:
            # 發送信號確保主進程知道伺服器正在關閉
            super().handle_exit(sig, frame)

        async def startup(self, sockets=None) -> None:
            await super().startup(sockets=sockets)
            # 伺服器啟動完成，設置事件
            print("✅ [Server Process] Uvicorn 已啟動，發送就緒信號。")
            ready_signal.set()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False
    )
    server = UvicornServer(config=config)

    print(f"🚀 [Server Process] Uvicorn 伺服器準備在 http://{host}:{port} 上啟動...")
    try:
        server.run()
    except KeyboardInterrupt:
        print("🛑 [Server Process] 收到退出信號，正在關閉伺服器。")
    finally:
        print("✅ [Server Process] 伺服器已關閉。")


def start_test_and_shutdown():
    """
    執行「啟動-測試-關閉」的自動化腳本。
    """
    print("==========================================================")
    print("🚀 執行「啟動-測試-關閉」自動化腳本...")
    print("==========================================================")

    # --- 步驟 1: 自我依賴安裝 ---
    print("\n--- [步驟 1/4] 正在檢查並安裝依賴 ---")
    try:
        import subprocess
        # 使用 -q (quiet) 和 -qq 來減少不必要的輸出
        print("📦 正在安裝核心依賴 (from requirements.txt)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-qq", "-r", "requirements.txt"], check=True)
        print("✅ 核心依賴安裝完成。")

        print("📦 正在安裝轉錄工作者依賴 (from requirements-worker.txt)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-qq", "-r", "requirements-worker.txt"], check=True)
        print("✅ 轉錄工作者依賴安裝完成。")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依賴安裝失敗，請檢查 requirements 檔案。錯誤: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ 找不到 requirements.txt 或 requirements-worker.txt，無法安裝依賴。")
        sys.exit(1)

    # --- 依賴安裝完畢，現在可以安全地匯入應用程式模組 ---
    import requests

    print("\n--- [步驟 2/4] 正在啟動背景服務 ---")
    # 在新架構中，背景工作由 phoenix_runner 透過 FastAPI 觸發，不再需要手動啟動執行緒。
    print("✅ [Watchdog] 新架構無需獨立啟動背景工作者。")

    # 1. 準備伺服器啟動
    host = "127.0.0.1"
    port = find_available_port()
    health_check_url = f"http://{host}:{port}/api/health"
    server_ready_signal = multiprocessing.Event() # 用於同步的事件

    print(f"✅ [Watchdog] 動態尋找到可用埠號: {port}")
    print(f"✅ [Watchdog] 健康檢查端點: {health_check_url}")

    # 3. 在獨立進程中啟動 Uvicorn 伺服器
    server_process = multiprocessing.Process(
        target=run_server,
        args=(host, port, server_ready_signal),
        daemon=True
    )
    server_process.start()
    print(f"✅ [Watchdog] Uvicorn 伺服器進程已啟動 (PID: {server_process.pid})。")

    # --- 步驟 3/4: 啟動看門狗監控與測試 ---
    print("\n--- [步驟 3/4] 看門狗已啟動，正在等待伺服器就緒並執行健康檢查 ---")

    # 等待 Uvicorn 發出「我已就緒」的信號，設定一個合理的超時
    server_started = server_ready_signal.wait(timeout=20)
    if not server_started:
        print("🚨 [Watchdog] 伺服器在20秒內未能啟動。測試失敗。")
        # 即使啟動失敗，也要嘗試清理進程
        if server_process.is_alive():
            server_process.terminate()
            server_process.join(2)
            if server_process.is_alive():
                server_process.kill()
        sys.exit(1)

    print("✅ [Watchdog] 伺服器已發出就緒信號，開始進行健康檢查...")
    consecutive_failures = 0
    max_failures = 3 # 連續失敗 3 次後判定為失敗
    check_interval = 7 # 每 7 秒檢查一次

    shutdown_initiated = False
    exit_code = 1 # 預設為失敗

    try:
        for i in range(max_failures + 1): # 最多檢查 max_failures 次
            if not server_process.is_alive():
                print("❌ [Watchdog] 偵測到伺服器進程在測試期間意外終止。")
                shutdown_initiated = True
                break

            try:
                # 執行健康檢查，設定較短的超時
                response = requests.get(health_check_url, timeout=3)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    # ==========================================================
                    # 核心變更：一旦檢查成功，立即觸發關閉流程
                    # ==========================================================
                    print("\n✅ [Watchdog] 健康檢查成功！伺服器運作正常。")
                    print("✅ [Watchdog] 測試通過，根據「啟動-測試-關閉」模式，將自動關閉所有服務。")
                    exit_code = 0 # 設定退出碼為成功
                    shutdown_initiated = True
                    break # 跳出迴圈，進入 finally 區塊進行關閉
                else:
                    raise ValueError(f"健康檢查回傳異常狀態: {response.status_code}")

            except requests.exceptions.RequestException as e:
                consecutive_failures += 1
                print(f"⚠️ [Watchdog] 健康檢查失敗 (第 {consecutive_failures}/{max_failures} 次): {e}")
                if consecutive_failures >= max_failures:
                    print(f"🚨 [Watchdog] 伺服器連續 {max_failures} 次無回應，測試失敗！")
                    shutdown_initiated = True
                    break

            if i < max_failures:
                 time.sleep(check_interval)


    except KeyboardInterrupt:
        print("\n🛑 [Watchdog] 收到使用者中斷信號 (Ctrl+C)。")
        exit_code = 1
    finally:
        # --- 步驟 4/4: 優雅關閉 ---
        print("\n--- [步驟 4/4] 正在關閉所有服務 ---")
        if server_process.is_alive():
            print("... 正在關閉 Uvicorn 伺服器進程...")
            server_process.terminate() # 傳送 SIGTERM
            server_process.join(timeout=5) # 等待 5 秒
            if server_process.is_alive():
                print("... 伺服器未能正常終止，將強制擊殺 (kill)。")
                server_process.kill() # 傳送 SIGKILL

        # worker_thread 是 daemon，會隨主進程退出而自動終止
        print("✅ 所有服務已成功關閉。")
        if exit_code == 0:
            print("\n🎉 測試成功完成！")
        else:
            print("\n💥 測試失敗或被中斷。")

        sys.exit(exit_code)


if __name__ == "__main__":
    # 在 Windows 和 macOS 上，multiprocessing 的預設啟動方法可能導致問題
    # 明確設定為 'spawn' 可以提高跨平台的穩定性
    multiprocessing.set_start_method("spawn", force=True)
    start_test_and_shutdown()
