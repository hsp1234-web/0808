# run_for_playwright.py
import subprocess
import sys
import time
import logging
import os
import re
import signal

# --- 複製自 local_run.py 的輔助函式 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('playwright_runner')

def cleanup_stale_processes():
    import psutil
    log.info("--- 正在檢查並清理舊的程序 ---")
    stale_process_names = ["orchestrator.py", "api_server.py", "db/manager.py"]
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
    log.info("--- 正在檢查並安裝依賴 (uv) ---")
    try:
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.info("未偵測到 uv，正在安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])

    requirements_files = ["requirements-server.txt", "requirements-worker.txt"]
    uv_command = [sys.executable, "-m", "uv", "pip", "install", "-q"]
    for req_file in requirements_files:
        uv_command.extend(["-r", req_file])
    subprocess.check_call(uv_command)
    log.info("✅ 所有依賴都已成功安裝。")

# --- 主啟動邏輯 ---
def main():
    orchestrator_proc = None
    # 使用一個全域旗標來處理 Ctrl+C
    keep_running = True

    def signal_handler(sig, frame):
        nonlocal keep_running
        log.info("\n收到終止信號... 正在準備關閉所有服務。")
        keep_running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        install_dependencies()
        cleanup_stale_processes()

        log.info("🚀 啟動協調器 (Playwright 測試模式)...")
        # 在模擬模式下啟動，並指定 E2E 測試所需的固定埠號
        cmd = [sys.executable, "orchestrator.py", "--mock", "--port", "42649"]

        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": 'utf-8',
        }
        if sys.platform != "win32":
            popen_kwargs['preexec_fn'] = os.setsid
        else:
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        orchestrator_proc = subprocess.Popen(cmd, **popen_kwargs)
        log.info(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        log.info("--- 正在等待 API 伺服器就緒 ---")
        # 注意：我們從 local_run.py 中得知，API URL 是由 orchestrator 打印出來的
        proxy_url_pattern = re.compile(r"PROXY_URL:\s*(http://127\.0\.0\.1:(\d+))")
        api_url = None
        timeout = 45
        start_time = time.time()

        for line in iter(orchestrator_proc.stdout.readline, ''):
            # 我們需要一個無緩衝的輸出來即時看到日誌
            # 在執行此腳本時，請使用 `PYTHONUNBUFFERED=1 python run_for_playwright.py`
            log.info(f"[Orchestrator]: {line.strip()}")
            url_match = proxy_url_pattern.search(line)
            if url_match:
                api_url = url_match.group(1)
                log.info(f"✅✅✅ 偵測到 API 服務 URL: {api_url} ✅✅✅")
                log.info("--- 伺服器已就緒，可以開始執行 Playwright 測試 ---")
                break
            if time.time() - start_time > timeout:
                raise RuntimeError("等待 API 伺服器就緒超時。")

        # 伺服器已就緒，現在進入等待狀態，直到收到終止信號
        while keep_running:
            # 檢查協調器是否意外退出
            if orchestrator_proc.poll() is not None:
                log.error("❌ 協調器程序意外終止！")
                break
            time.sleep(1)

    except Exception as e:
        log.critical(f"💥 啟動器發生致命錯誤: {e}", exc_info=True)
    finally:
        if orchestrator_proc and orchestrator_proc.poll() is None:
            log.info("--- 正在終止協調器及其所有子程序 ---")
            try:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(orchestrator_proc.pid), signal.SIGTERM)
                else:
                    orchestrator_proc.terminate()
                orchestrator_proc.wait(timeout=10)
                log.info("✅ 協調器程序已成功終止。")
            except (ProcessLookupError, TimeoutExpired) as e:
                log.error(f"終止程序時發生錯誤: {e}。可能需要手動清理。")
                orchestrator_proc.kill()

        log.info("🏁 Playwright 服務啟動器已關閉。")

if __name__ == "__main__":
    main()
