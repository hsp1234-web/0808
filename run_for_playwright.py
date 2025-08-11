import subprocess
import sys
import time
import logging
import os
import signal
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('playwright_runner')

def install_dependencies():
    log.info("--- 正在安裝 Python 依賴 ---")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements-server.txt", "-r", "requirements-worker.txt"])
    log.info("✅ Python 依賴安裝成功。")
    log.info("--- 正在安裝 Node.js 依賴 ---")
    subprocess.check_call(["bun", "install"])
    log.info("✅ Node.js 依賴安裝成功。")

def main():
    procs = []
    log_files = {}

    def cleanup():
        log.info("--- 正在終止所有子程序 ---")
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=5)
        for f in log_files.values():
            f.close()
        log.info("✅ 清理完成。")

    signal.signal(signal.SIGINT, lambda s, f: cleanup())
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())

    try:
        install_dependencies()
        import requests

        # 設定環境變數
        env = os.environ.copy()
        env['GOOGLE_API_KEY'] = 'AIzaSyDT62J3wo1ckaQkF2Pve9SvpBreZh3-dnM'
        env['FORCE_MOCK_TRANSCRIBER'] = 'true'
        # The server itself runs in "real" mode to allow real YT/Gemini calls
        env['API_MODE'] = 'mock'

        # 清理日誌
        log_dir = Path("logs")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)
        log_dir.mkdir()

        # 啟動資料庫管理器
        log.info("--- 正在啟動資料庫管理器 ---")
        db_log_file = open("logs/db_manager.log", "w")
        log_files['db'] = db_log_file
        db_proc = subprocess.Popen(
            [sys.executable, "db/manager.py"],
            env=env,
            stdout=db_log_file,
            stderr=db_log_file
        )
        procs.append(db_proc)
        log.info(f"✅ 資料庫管理器已啟動 (PID: {db_proc.pid})。")
        time.sleep(3) # 等待資料庫管理器啟動

        # 啟動 API 伺服器
        log.info("--- 正在啟動 API 伺服器 ---")
        api_log_file = open("logs/api_server.log", "w")
        log_files['api'] = api_log_file
        api_proc = subprocess.Popen(
            [sys.executable, "api_server.py", "--port", "42649"],
            env=env,
            stdout=api_log_file,
            stderr=api_log_file
        )
        procs.append(api_proc)
        log.info(f"✅ API 伺服器已啟動 (PID: {api_proc.pid})。")

        # 等待 API 伺服器就緒
        log.info("--- 等待 API 伺服器就緒 ---")
        api_health_url = "http://127.0.0.1:42649/api/health"
        timeout = 60
        start_time = time.time()
        server_ready = False
        while time.time() - start_time < timeout:
            try:
                response = requests.get(api_health_url)
                if response.status_code == 200:
                    log.info("✅✅✅ API 伺服器已就緒！ ✅✅✅")
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)

        if not server_ready:
            raise RuntimeError("等待 API 伺服器就緒超時。")

        log.info("--- 可以開始執行 Playwright 測試 ---")
        # In a real CI/CD, the test runner would be a separate command.
        # Here, we just wait for a signal to terminate.
        while True:
            time.sleep(1)

    except Exception as e:
        log.critical(f"💥 啟動器發生致命錯誤: {e}", exc_info=True)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
