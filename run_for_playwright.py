# run_for_playwright.py
import subprocess
import sys
import time
import logging
import os
import signal
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('playwright_runner')

# --- 動態設定 circus.ini ---
def create_circus_config():
    """
    動態產生 circus.ini 檔案，確保使用正確的 Python 可執行檔。
    """
    python_executable = sys.executable
    log.info(f"將使用此 Python 執行檔來運行服務: {python_executable}")

    config_content = f"""
[circus]
check_delay = 5
endpoint = tcp://127.0.0.1:5555
pubsub_endpoint = tcp://127.0.0.1:5556
stats_endpoint = tcp://127.0.0.1:5557
httpd = False

[watcher:db_manager]
cmd = {python_executable} db/manager.py
working_dir = /app
stdout_stream.class = FileStream
stdout_stream.filename = /app/logs/db_manager.log
stderr_stream.class = FileStream
stderr_stream.filename = /app/logs/db_manager.err
autostart = True
restart_on_error = True

[watcher:api_server]
cmd = {python_executable} api_server.py --port 42649
working_dir = /app
stdout_stream.class = FileStream
stdout_stream.filename = /app/logs/api_server.log
stderr_stream.class = FileStream
stderr_stream.filename = /app/logs/api_server.err
autostart = True
restart_on_error = True
    """

    config_path = Path("circus.ini")
    config_path.write_text(config_content.strip())
    log.info(f"✅ 已成功產生設定檔: {config_path}")


def cleanup_stale_processes():
    """清理任何可能由先前執行殘留的舊程序。"""
    import psutil
    log.info("--- 正在檢查並清理舊的程序 ---")
    stale_process_names = ["circusd", "api_server.py", "db/manager.py"]
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
    """安裝所有必要的 Python 和 Node.js 依賴。"""
    log.info("--- 步驟 1/5: 正在安裝 Python 依賴 (uv) ---")
    try:
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.info("未偵測到 uv，正在安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])

    # JULES'S DEBUGGING: 只安裝伺服器依賴，以排除 worker 依賴的干擾
    log.warning("!!! 偵錯模式：僅安裝伺服器依賴 !!!")
    requirements_files = ["requirements-server.txt"]
    uv_command = [sys.executable, "-m", "uv", "pip", "install", "-q"]
    for req_file in requirements_files:
        if os.path.exists(req_file):
            uv_command.extend(["-r", req_file])
    subprocess.check_call(uv_command)
    log.info("✅ 所有 Python 依賴都已成功安裝。")

    log.info("--- 步驟 2/5: 正在安裝 Node.js 依賴 (bun) ---")
    try:
        subprocess.check_call(["bun", "install"])
        log.info("✅ Node.js 依賴安裝成功。")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log.error(f"❌ bun install 失敗: {e}")
        log.error("請確保 Bun 已安裝並在您的 PATH 中。")
        sys.exit(1)

# --- 主啟動邏輯 ---
def main():
    keep_running = True

    def signal_handler(sig, frame):
        nonlocal keep_running
        log.info("\n收到終止信號... 正在準備關閉所有服務。")
        keep_running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 步驟 1: 清理日誌目錄，確保我們看到的是最新的日誌
        log_dir = Path("logs")
        if log_dir.exists():
            import shutil
            shutil.rmtree(log_dir)
            log.info(f"✅ 已清理舊的日誌目錄: {log_dir}")
        log_dir.mkdir()

        install_dependencies()

        # JULES'S FIX: Import requests after it has been installed.
        import requests

        cleanup_stale_processes()

        log.info("--- 步驟 3/5: 動態產生 Circus 設定 ---")
        create_circus_config()

        log.info("--- 步驟 4/5: 設定模擬模式並啟動 Circusd ---")
        log.info("為測試環境設定 API_MODE=mock")
        os.environ['API_MODE'] = 'mock'
        circus_cmd = [sys.executable, "-m", "circus.circusd", "circus.ini"]
        subprocess.Popen(circus_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("✅ Circusd 已啟動。")

        log.info("--- 步驟 5/5: 等待 API 伺服器就緒 ---")
        api_health_url = "http://127.0.0.1:42649/api/health"
        timeout = 45
        start_time = time.time()
        server_ready = False

        while time.time() - start_time < timeout:
            try:
                response = requests.get(api_health_url)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    log.info(f"✅✅✅ API 伺服器已在 {api_health_url} 上就緒！ ✅✅✅")
                    log.info("--- 伺服器已就緒，可以開始執行 Playwright 測試 ---")
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)

        if not server_ready:
            raise RuntimeError(f"等待 API 伺服器在 {api_health_url} 上就緒超時。")

        while keep_running:
            try:
                status_res = subprocess.check_output([sys.executable, "-m", "circus.circusctl", "status"])
                if b"stopped" in status_res:
                    log.error("❌ Circus 報告有服務已停止！請檢查日誌 /logs/*.log")
                    break
            except (subprocess.CalledProcessError, FileNotFoundError):
                log.error("❌ 無法獲取 circus 狀態，可能已崩潰。")
                break
            time.sleep(2)

    except Exception as e:
        log.critical(f"💥 啟動器發生致命錯誤: {e}", exc_info=True)
    finally:
        log.info("--- 正在透過 circusctl 關閉所有服務 ---")
        try:
            subprocess.check_call([sys.executable, "-m", "circus.circusctl", "quit"])
            log.info("✅ 所有服務已成功關閉。")
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.error("⚠️ 無法優雅地關閉 circus。將執行強制清理。")
            cleanup_stale_processes()

        log.info("🏁 Playwright 服務啟動器已關閉。")

if __name__ == "__main__":
    main()
