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
        # 安裝必要的系統依賴
        log.info("--- [WebServer] 正在安裝 'psmisc' 和 'ffmpeg'... ---")
        subprocess.run(['sudo', 'apt-get', 'update'], check=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'psmisc', 'ffmpeg'], check=True)
        log.info("--- [WebServer] 'psmisc' 和 'ffmpeg' 安裝成功。 ---")

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

        env = os.environ.copy()
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        src_path = os.path.join(project_root, 'src')
        env['PYTHONPATH'] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        server_cmd = [
            sys.executable,
            "-u",
            "src/core/orchestrator.py",
            "--port",
            "42649"
        ]

        server_proc = subprocess.Popen(server_cmd, stdout=sys.stdout, stderr=sys.stderr, env=env)

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
