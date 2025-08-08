# scripts/launch.py
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - [%(levelname)s] %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger('launch')

# --- 設定 sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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

def main():
    """
    應用程式主入口（v2 - 解耦架構）。
    這個版本不再管理背景工作者，只負責安裝依賴和啟動 FastAPI 伺服器。
    """
    parser = argparse.ArgumentParser(description="啟動 Uvicorn 伺服器。")
    parser.add_argument("--port", type=int, default=8000, help="Uvicorn 伺服器要監聽的埠號。")
    args = parser.parse_args()

    # --- 步驟 1: 依賴安裝 ---
    # 在新架構中，依賴被烘烤到獨立環境中。
    # 但主應用程式 (FastAPI) 仍有其依賴。
    log.info("--- [1/2] 正在檢查並安裝主應用程式依賴 ---")
    try:
        requirements_path = os.path.join(project_root, 'requirements.txt')
        if os.path.exists(requirements_path):
            log.info("📦 正在安裝核心依賴 (from requirements.txt)...")
            # 使用 uv 來加速安裝
            subprocess.run(["uv", "pip", "install", "-q", "-r", requirements_path, "--system"], check=True)
            log.info("✅ 核心依賴安裝完成。")
        else:
            log.warning("未找到 requirements.txt，跳過依賴安裝。")
    except subprocess.CalledProcessError as e:
        log.critical(f"❌ 依賴安裝失敗: {e}")
        sys.exit(1)
    except FileNotFoundError:
        log.warning("找不到 'uv' 命令，將使用 'pip'。")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", requirements_path], check=True)


    # --- 步驟 2: 啟動 Uvicorn 伺服器 ---
    log.info("--- [2/2] 正在啟動 FastAPI 伺服器 ---")

    # 在主執行緒中直接啟動 Uvicorn
    # 這樣可以接收到 Ctrl+C 等中斷信號
    try:
        # 發送就緒信號給 Colab
        # 我們在 Uvicorn 啟動前發送，因為 uvicorn.run 會阻塞
        # Colab 端應該使用 wait_for_server_ready 的方式來等待
        log.info("✅ 伺服器即將啟動...")
        print("PHOENIX_SERVER_READY_FOR_COLAB", flush=True)

        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=args.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        log.info("\n收到使用者中斷信號 (Ctrl+C)... 正在關閉應用程式。")
    finally:
        log.info("應用程式已關閉。再見！")
        sys.exit(0)

if __name__ == "__main__":
    main()
