import subprocess
import sys
from pathlib import Path
import time
import logging
import os
import signal
import psutil
import requests

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('run_server_for_playwright')

# 將 src 目錄加入 Python 路徑
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

CIRCUS_PID = None

def cleanup_stale_processes():
    """清理任何可能由先前執行殘留的舊程序。"""
    log.info("--- 正在檢查並清理舊的程序 ---")
    # 清理 circusd 和它可能啟動的任何 python 服務
    stale_process_names = ["circusd", "src/api/api_server.py", "src/db/manager.py"]
    cleaned_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if not cmdline: continue
            if any(name in ' '.join(cmdline) for name in stale_process_names):
                log.warning(f"偵測到殘留的程序: PID={proc.pid}。正在終止它...")
                proc.kill()
                cleaned_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    log.info(f"✅ 清理完成。共終止 {cleaned_count} 個程序。")

def install_dependencies():
    """安裝所有必要的 Python 依賴套件。"""
    log.info("--- 正在檢查並安裝 Python 依賴 ---")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        log.info("✅ 所有 Python 依賴都已成功安裝。")
    except subprocess.CalledProcessError as e:
        log.error(f"❌ 安裝依賴時發生錯誤: {e}")
        raise

def handle_shutdown_signal(signum, frame):
    """處理終止信號，以優雅地關閉服務。"""
    log.warning(f"接收到信號 {signum}。正在準備關閉服務...")
    # 這裡觸發的清理會在 main 函式的 finally 區塊中執行
    # 引發一個 SystemExit 可以讓主迴圈中斷
    sys.exit(0)

def main():
    """
    一個為 Playwright E2E 測試設計的、穩健的伺服器啟動器。
    它會：
    1. 清理舊程序。
    2. 安裝依賴。
    3. 使用 Circus 啟動後端服務（API 為 mock 模式）。
    4. 等待服務就緒。
    5. 保持運行，直到收到來自 Playwright 的終止信號。
    6. 優雅地關閉所有服務。
    """
    global CIRCUS_PID
    circus_proc = None

    # 註冊信號處理器
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    try:
        # 步驟 1 & 2: 清理與安裝
        cleanup_stale_processes()
        install_dependencies()

        # 步驟 3: 準備並啟動 Circus
        # 我們需要一個修改版的 circus.ini，以確保 API 伺服器以模擬模式啟動
        # 最簡單的方法是通過環境變數來控制
        log.info("--- 正在啟動 Circus 來管理後端服務 (API 為 MOCK 模式) ---")
        proc_env = os.environ.copy()
        proc_env["API_MODE"] = "mock"

        # 確保 circus.ini 存在並替換變數
        template_path = "config/circus.ini.template"
        config_path = "circus.ini"
        if os.path.exists(template_path):
            log.info("從範本建立 circus.ini 並替換 PYTHON_EXEC...")
            with open(template_path, 'r') as f_template:
                content = f_template.read()

            # 替換預留位置
            # 使用 sys.executable 確保我們用的是執行此腳本的同一個 Python 直譯器
            content = content.replace("%%PYTHON_EXEC%%", sys.executable)

            with open(config_path, 'w') as f_config:
                f_config.write(content)
        else:
            raise FileNotFoundError(f"找不到 circus.ini 的範本檔案: {template_path}")

        circus_cmd = [sys.executable, "-m", "circus.circusd", "circus.ini"]
        # 將日誌導向檔案以便除錯
        circus_log_file = open("circus.log", "w")
        circus_proc = subprocess.Popen(circus_cmd, env=proc_env, stdout=circus_log_file, stderr=subprocess.STDOUT)
        CIRCUS_PID = circus_proc.pid
        log.info(f"✅ Circusd 已啟動 (PID: {CIRCUS_PID})。日誌位於 circus.log。")

        # 步驟 4: 等待 API 伺服器就緒
        log.info("--- 正在等待 API 伺服器就緒 ---")
        api_port = 42649 # 從 circus.ini 或 playbook 得知
        api_health_url = f"http://127.0.0.1:{api_port}/api/health"
        timeout = time.time() + 60 # 60 秒超時
        server_ready = False
        while time.time() < timeout:
            try:
                response = requests.get(api_health_url, timeout=2)
                if response.status_code == 200:
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)
            except requests.Timeout:
                log.warning("健康檢查請求超時，正在重試...")

        if not server_ready:
            raise RuntimeError(f"等待 API 伺服器在 {api_health_url} 上就緒超時。請檢查 circus.log。")

        log.info(f"✅✅✅ 伺服器已在埠 {api_port} 上就緒。Playwright 測試現在可以開始了。✅✅✅")

        # 步驟 5: 保持腳本運行，等待終止信號
        # 這是一個簡單的方法，讓腳本在主執行緒中保持活動狀態
        while True:
            time.sleep(1)

    except (Exception, SystemExit) as e:
        if isinstance(e, SystemExit) and e.code == 0:
            log.info("收到正常的退出請求。")
        else:
            log.critical(f"💥 伺服器啟動器發生錯誤: {e}", exc_info=True)
            # 以非零狀態碼退出，告知 Playwright 啟動失敗
            sys.exit(1)
    finally:
        log.info("--- 正在關閉所有服務 ---")
        if CIRCUS_PID:
            try:
                # 使用 circusctl 來優雅地關閉
                log.info("正在透過 circusctl 發送關閉指令...")
                subprocess.check_call([sys.executable, "-m", "circus.circusctl", "quit"])
                # 等待 circusd 程序結束
                circus_proc.wait(timeout=10)
                log.info("✅ Circus 服務已成功關閉。")
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as err:
                log.error(f"⚠️ 無法優雅地關閉 circus ({err})。將執行強制清理。")
                cleanup_stale_processes()
        else:
            # 如果 circus 從未成功啟動，也執行一次清理以防萬一
            cleanup_stale_processes()

        if 'circus_log_file' in locals() and not circus_log_file.closed:
            circus_log_file.close()

        log.info("🏁 伺服器啟動器已完全關閉。")


if __name__ == "__main__":
    main()
