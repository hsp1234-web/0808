import subprocess
import sys
# JULES: 將 src 目錄加入 Python 路徑，以確保可以找到其下的模組
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
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
    # JULES: 移除 worker 依賴，僅安裝伺服器依賴，以避免安裝 torch
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "src/requirements-server.txt"])
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
        # JULES: 移除了硬編碼的 API 金鑰，改用一個無害的模擬金鑰，因為此腳本在模擬模式下運行。
        env['GOOGLE_API_KEY'] = 'playwright-mock-api-key'
        env['FORCE_MOCK_TRANSCRIBER'] = 'true'
        # The server itself runs in "real" mode to allow real YT/Gemini calls
        env['API_MODE'] = 'mock'

        # 清理日誌和上傳檔案
        log_dir = Path("logs")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)
        log_dir.mkdir()

        upload_dir = Path("uploads")
        if upload_dir.exists():
            import shutil
            shutil.rmtree(upload_dir)
        upload_dir.mkdir()

        # JULES'S FIX: Clean up the database file to ensure test isolation
        db_file = Path("src/db/queue.db")
        if db_file.exists():
            log.info(f"--- 正在清理舊的資料庫檔案 ({db_file}) ---")
            db_file.unlink()
            log.info("✅ 舊資料庫已刪除。")

        # 啟動資料庫管理器
        log.info("--- 正在啟動資料庫管理器 ---")
        db_stdout_file = open("logs/db_manager.log", "w")
        db_stderr_file = open("logs/db_manager.err", "w")
        log_files['db_stdout'] = db_stdout_file
        log_files['db_stderr'] = db_stderr_file
        db_proc = subprocess.Popen(
            [sys.executable, "src/db/manager.py"],
            env=env,
            stdout=db_stdout_file,
            stderr=db_stderr_file
        )
        procs.append(db_proc)
        log.info(f"✅ 資料庫管理器已啟動 (PID: {db_proc.pid})。")
        time.sleep(3) # 等待資料庫管理器啟動

        # 啟動 API 伺服器
        log.info("--- 正在啟動 API 伺服器 ---")
        api_stdout_file = open("logs/api_server.log", "w")
        api_stderr_file = open("logs/api_server.err", "w")
        log_files['api_stdout'] = api_stdout_file
        log_files['api_stderr'] = api_stderr_file
        api_proc = subprocess.Popen(
            [sys.executable, "src/api_server.py", "--port", "42649"],
            env=env,
            stdout=api_stdout_file,
            stderr=api_stderr_file
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
