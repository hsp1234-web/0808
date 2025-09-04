import subprocess
import sys
import time
import logging
import os
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('run_server_for_playwright_v2')

def main():
    # --- v2 環境準備 ---
    V2_PORT = 42650
    try:
        # 安裝 psmisc 以確保 fuser 指令存在
        log.info("--- [WebServer v2] 正在安裝 'psmisc' (提供 fuser)... ---")
        subprocess.run(['sudo', 'apt-get', 'update'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'psmisc'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info("--- [WebServer v2] 'psmisc' 安裝成功。 ---")

        log.info(f"--- [WebServer v2] 正在清理目標埠號 {V2_PORT}... ---")
        subprocess.run(['fuser', '-k', f'{V2_PORT}/tcp'], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        log.error(f"--- [WebServer v2] 環境準備階段發生錯誤: {e} ---")

    server_proc = None

    def handle_shutdown_signal(signum, frame):
        nonlocal server_proc
        log.warning(f"--- [WebServer v2] 接收到信號 {signum}，正在終止 v2 伺服器... ---")
        if server_proc and server_proc.poll() is None:
            server_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    try:
        log.info("--- [WebServer v2] 正在啟動 orchestrator_v2.py ---")

        env = os.environ.copy()
        # 強制設定 API_MODE 為 mock for testing
        env['API_MODE'] = 'mock'

        # 設定 v2 的 PYTHONPATH
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        src_path = os.path.join(project_root, 'src')
        env['PYTHONPATH'] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        server_cmd = [
            sys.executable,
            "-u",
            "src/core/orchestrator_v2.py",
            "--port",
            str(V2_PORT),
            "--mock"
        ]

        server_proc = subprocess.Popen(server_cmd, stdout=sys.stdout, stderr=sys.stderr, env=env)

        log.info(f"--- [WebServer v2] v2 Orchestrator 已啟動 (PID: {server_proc.pid}) ---")
        log.info("--- [WebServer v2] Playwright 將接管並等待健康檢查 URL... ---")

        while True:
            time.sleep(1)

    except Exception as e:
        log.critical(f"--- [WebServer v2] 💥 啟動器發生錯誤: {e} ---", exc_info=True)
        sys.exit(1)
    finally:
        log.info("--- [WebServer v2] 🏁 v2 伺服器腳本結束。 ---")

if __name__ == "__main__":
    main()
