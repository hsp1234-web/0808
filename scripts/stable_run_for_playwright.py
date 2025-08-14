# stable_run_for_playwright.py
import subprocess
import sys
from pathlib import Path
import time
import logging
import os
import signal
import requests
import shutil
import socket

# =====================================================================================
# 穩定版 Playwright 伺服器啟動腳本
#
# 核心設計理念：
# 根據 docs/BUG.md 的分析，此沙箱環境存在一個致命 BUG：
# 任何被呼叫的 Python 函式，若其定義中包含 `subprocess.Popen`，會導致解譯器無聲地掛起。
#
# 此腳本的規避策略是：
# 1. 將 `subprocess.Popen` 的呼叫移出任何函式定義，直接在腳本的「全域範圍」執行。
#    這旨在繞過 Python 解譯器對「函式呼叫」的攔截 BUG。
# 2. 移除所有不必要的複雜性，例如依賴安裝，因為這將由使用者在測試流程中手動完成。
# 3. 專注於核心職責：清理環境、以穩定方式啟動背景服務、等待服務就緒、並保持運行。
# =====================================================================================

# --- 1. 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('stable_playwright_runner')

# 將 src 目錄加入 Python 路徑
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

# --- 2. 環境與變數設定 ---
API_PORT = 42649
API_HEALTH_URL = f"http://127.0.0.1:{API_PORT}/api/health"
LOG_DIR = Path("logs")
UPLOAD_DIR = Path("uploads")
DB_FILE = SRC_DIR / "db" / "queue.db"

# 設定子程序環境變數
CHILD_PROCESS_ENV = os.environ.copy()
CHILD_PROCESS_ENV['API_MODE'] = 'mock'
CHILD_PROCESS_ENV['FORCE_MOCK_TRANSCRIBER'] = 'true'
CHILD_PROCESS_ENV['PYTHONPATH'] = str(SRC_DIR)

# --- 3. 清理與啟動程序 (在全域範圍執行) ---
procs = []
log_files = {}

# 定義清理函式 (此函式本身不含 Popen，是安全的)
def cleanup(signum=None, frame=None):
    log.info("--- 正在終止所有子程序 ---")
    # 從後往前終止，先停 API server 再停 DB
    for p in reversed(procs):
        try:
            p.terminate()
        except ProcessLookupError:
            pass # 程序可能已經不存在

    # 等待程序確實終止
    for p in reversed(procs):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.warning(f"程序 {p.pid} 未能在 5 秒內終止，強制結束。")
            p.kill()
        except ProcessLookupError:
            pass

    # 關閉日誌檔案
    for f in log_files.values():
        f.close()
    log.info("✅ 清理完成。")
    # 收到信號後正常退出
    sys.exit(0)

# 註冊信號處理器
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

try:
    # 清理舊的日誌和上傳檔案
    log.info("--- 正在清理舊的日誌和上傳目錄 ---")
    if LOG_DIR.exists():
        shutil.rmtree(LOG_DIR)
    LOG_DIR.mkdir()

    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir()
    log.info("✅ 清理完成。")

    # 清理舊的資料庫檔案
    if DB_FILE.exists():
        log.info(f"--- 正在清理舊的資料庫檔案 ({DB_FILE}) ---")
        DB_FILE.unlink()
        log.info("✅ 舊資料庫已刪除。")

    # 啟動資料庫管理器
    log.info("--- 正在啟動資料庫管理器 ---")
    db_stdout_file = open(LOG_DIR / "db_manager.log", "w")
    db_stderr_file = open(LOG_DIR / "db_manager.err", "w")
    log_files['db_stdout'] = db_stdout_file
    log_files['db_stderr'] = db_stderr_file

    db_proc = subprocess.Popen(
        [sys.executable, str(SRC_DIR / "db" / "manager.py")],
        env=CHILD_PROCESS_ENV,
        stdout=db_stdout_file,
        stderr=db_stderr_file
    )
    procs.append(db_proc)
    log.info(f"✅ 資料庫管理器已啟動 (PID: {db_proc.pid})。")

    # --- 等待資料庫管理器就緒 (取代不穩定的 time.sleep) ---
    db_manager_port = 49999
    log.info(f"--- 等待資料庫管理器在埠號 {db_manager_port} 上就緒 ---")
    retries = 40
    for i in range(retries):
        try:
            with socket.create_connection(("127.0.0.1", db_manager_port), timeout=1):
                log.info(f"✅ 資料庫管理器在埠號 {db_manager_port} 上已可連線。")
                break
        except (ConnectionRefusedError, socket.timeout):
            if i < retries - 1:
                log.info(f"資料庫管理器尚未就緒，{i+1}/{retries} 次嘗試，1 秒後重試...")
                time.sleep(1)
            else:
                log.critical(f"💥 等待資料庫管理器就緒超時。")
                raise RuntimeError("DB Manager failed to start in time.")

    # 啟動 API 伺服器
    log.info("--- 正在啟動 API 伺服器 ---")
    api_stdout_file = open(LOG_DIR / "api_server.log", "w")
    api_stderr_file = open(LOG_DIR / "api_server.err", "w")
    log_files['api_stdout'] = api_stdout_file
    log_files['api_stderr'] = api_stderr_file

    api_proc = subprocess.Popen(
        [sys.executable, str(SRC_DIR / "api" / "api_server.py"), "--port", str(API_PORT)],
        env=CHILD_PROCESS_ENV,
        stdout=api_stdout_file,
        stderr=api_stderr_file
    )
    procs.append(api_proc)
    log.info(f"✅ API 伺服器已啟動 (PID: {api_proc.pid})。")

    # 等待 API 伺服器就緒
    log.info(f"--- 等待 API 伺服器就緒 ({API_HEALTH_URL}) ---")
    timeout = 60
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < timeout:
        try:
            response = requests.get(API_HEALTH_URL, timeout=1)
            if response.status_code == 200:
                log.info("✅✅✅ API 伺服器已就緒！ ✅✅✅")
                server_ready = True
                break
        except requests.ConnectionError:
            log.info("伺服器尚未就緒，1 秒後重試...")
            time.sleep(1)
        except requests.RequestException as e:
            log.warning(f"健康檢查請求發生錯誤: {e}")
            time.sleep(1)

    if not server_ready:
        log.critical("💥 等待 API 伺服器就緒超時。")
        raise RuntimeError("API server failed to start in time.")

    log.info("--- 所有服務已啟動。腳本將保持運行以維持子程序。按 Ctrl+C 結束。 ---")
    while True:
        time.sleep(10) # 降低 CPU 使用率

except Exception as e:
    log.critical(f"💥 啟動器發生致命錯誤: {e}", exc_info=True)

finally:
    # 確保在發生任何未預期錯誤時都能執行清理
    cleanup()
