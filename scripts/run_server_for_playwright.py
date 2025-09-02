import subprocess
import sys
import time
import logging
import os
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('run_server_for_playwright')

def main():
    # --- 依賴與環境準備 ---
    try:
        # 安裝 psmisc 以確保 fuser 指令存在
        log.info("--- [WebServer] 正在安裝 'psmisc' (提供 fuser)... ---")
        subprocess.run(['sudo', 'apt-get', 'update'], check=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'psmisc'], check=True)
        log.info("--- [WebServer] 'psmisc' 安裝成功。 ---")

        # 清理目標埠號
        log.info("--- [WebServer] 正在清理目標埠號 42649... ---")
        subprocess.run(['fuser', '-k', '42649/tcp'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        log.error(f"--- [WebServer] 環境準備階段發生錯誤: {e} ---")
        # 即使準備失敗，也繼續嘗試，讓主要邏輯來處理後續錯誤

    server_proc = None

    def handle_shutdown_signal(signum, frame):
        nonlocal server_proc
        log.warning(f"--- [WebServer] 接收到信號 {signum}，正在終止伺服器... ---")
        if server_proc and server_proc.poll() is None:
            server_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    try:
        log.info("--- [WebServer] 正在啟動 orchestrator.py ---")

        # --- 最終修復 (2025-09-02) ---
        # 根本原因分析：直接在 subprocess.Popen 中設定 env={'PYTHONPATH': ...} 的方式，
        # 在經過 bun -> cross-env -> playwright 的複雜呼叫鏈後，似乎並未被子程序正確繼承。
        # 唯一的、最可靠的解決方法是像在 shell 中一樣，將環境變數的設定作為指令本身的一部分。
        # 我們使用 `shell=True` 來執行一個包含環境變數設定的完整 shell 指令。
        # 雖然 `shell=True` 通常有安全隱憂，但在這個所有路徑和參數都由我們內部控制的
        # 特定情境下，是安全且必要的。

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        src_path = os.path.join(project_root, 'src')
        orchestrator_path = os.path.join(project_root, 'src', 'core', 'orchestrator.py')

        # 將指令組合成一個 shell 字串
        command_string = (
            f"PYTHONPATH={src_path} API_MODE=mock "
            f"{sys.executable} -u {orchestrator_path} --port 42649"
        )

        log.info(f"--- [WebServer] 執行指令: {command_string} ---")

        # 使用 shell=True 執行
        server_proc = subprocess.Popen(command_string, stdout=sys.stdout, stderr=sys.stderr, shell=True)

        log.info(f"--- [WebServer] Orchestrator 已啟動 (PID: {server_proc.pid}) ---")
        log.info("--- [WebServer] Playwright 將接管並等待健康檢查 URL... ---")

        # 保持主腳本存活，以便背景工作可以持續執行
        # 信號處理程序 (handle_shutdown_signal) 將會處理清理工作
        while True:
            time.sleep(1)

    except Exception as e:
        log.critical(f"--- [WebServer] 💥 啟動器發生錯誤: {e} ---", exc_info=True)
        sys.exit(1)
    finally:
        log.info("--- [WebServer] 🏁 伺服器腳本結束。 ---")

if __name__ == "__main__":
    main()
