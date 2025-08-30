import subprocess
import sys
import time
import logging
import os
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('run_server_for_playwright')

def main():
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

        # 強制使用 Playwright 期望的固定埠號 42649
        server_cmd = [
            sys.executable,
            "-u",  # JULES: Force unbuffered stdout to prevent logs from getting stuck in CI
            "src/core/orchestrator.py",
            "--port",
            "42649"
        ]

        # 將日誌直接流到此程序的 stdout/stderr，以便 Playwright 可以捕獲它們
        server_proc = subprocess.Popen(server_cmd, stdout=sys.stdout, stderr=sys.stderr)

        log.info(f"--- [WebServer] Orchestrator 已啟動 (PID: {server_proc.pid}) ---")
        log.info("--- [WebServer] Playwright 將接管並等待健康檢查 URL... ---")

        server_proc.wait()

    except Exception as e:
        log.critical(f"--- [WebServer] 💥 啟動器發生錯誤: {e} ---", exc_info=True)
        sys.exit(1)
    finally:
        log.info("--- [WebServer] 🏁 伺服器腳本結束。 ---")

if __name__ == "__main__":
    main()
