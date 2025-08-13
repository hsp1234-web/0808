# run_tests.py (統一測試啟動器)
import subprocess
import sys
import time
import logging
import os
from pathlib import Path
import signal

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('TestRunner')

def install_dependencies():
    """使用 uv 安裝所有必要的依賴套件。"""
    log.info("--- 正在檢查並安裝依賴 (uv 優化流程) ---")
    try:
        # 檢查 uv 是否已安裝
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.info("未偵測到 uv，正在安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])

    # 安裝所有 Python 依賴
    requirements_file = "requirements.txt"
    log.info(f"正在使用 uv 安裝依賴: {requirements_file}...")
    # 使用 -q 來減少不必要的輸出
    uv_command = [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", requirements_file]

    # 最關鍵的一步：以可編輯模式安裝目前的專案
    # 這會讓 pytest 和其他工具能夠正確地找到 src 目錄下的模組
    uv_command.extend(["-e", "."])
    log.info(f"正在以可編輯模式安裝專案...")

    # 執行安裝指令
    subprocess.check_call(uv_command)
    log.info("✅ 所有 Python 依賴都已成功安裝。")


def cleanup_stale_processes():
    """清理任何可能由先前執行殘留的舊程序，以確保測試環境乾淨。"""
    import psutil
    log.info("--- 正在檢查並清理舊的程序 ---")
    # 注意：'circusd' 也被加入到清理列表，以處理未正常關閉的 circus 管理器
    stale_process_names = ["circusd", "src/api/api_server.py", "src/db/manager.py"]
    cleaned_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 檢查程序名稱或命令列是否匹配
            cmdline = proc.info.get('cmdline')
            if not cmdline:
                continue
            # 在所有作業系統上，都檢查命令列中是否有目標腳本名稱
            if any(name in ' '.join(cmdline) for name in stale_process_names):
                log.warning(f"偵測到殘留的程序: PID={proc.pid} ({' '.join(cmdline)})。正在終止它...")
                proc.kill() # 強制終止
                cleaned_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 程序可能在我們檢查後就消失了，這是正常的
            pass
    if cleaned_count > 0:
        log.info(f"✅ 清理完成。共終止 {cleaned_count} 個程序。")
    else:
        log.info("✅ 環境乾淨，未發現殘留程序。")

def main():
    """
    主函式，協調測試的設定、執行和清理。
    """
    log.info("啟動統一測試啟動器...")

    # 步驟 0: 安裝依賴
    install_dependencies()

    # 步驟 1: 清理環境
    cleanup_stale_processes()
    # JULES'S FIX: Correct path for src-layout
    db_file = Path("src/db/queue.db")
    if db_file.exists():
        log.info(f"--- 正在清理舊的資料庫檔案 ({db_file}) ---")
        db_file.unlink()
        log.info("✅ 舊資料庫已刪除。")

    # 步驟 2: 在 try/finally 區塊中啟動服務，以確保它們總能被關閉
    circus_proc = None
    exit_code = 1 # 預設結束代碼為 1 (失敗)
    try:
        import requests
        import pytest

        log.info("--- 正在動態生成 circus.ini 設定檔 ---")
        template_path = Path("config/circus.ini.template")
        config_path = Path("config/circus.ini")
        template_content = template_path.read_text(encoding='utf-8')
        # 將預留位置 %%PYTHON_EXEC%% 替換為當前 Python 直譯器的絕對路徑
        config_content = template_content.replace("%%PYTHON_EXEC%%", sys.executable)
        config_path.write_text(config_content, encoding='utf-8')
        log.info(f"✅ config/circus.ini 已根據 {sys.executable} 動態生成。")

        log.info("--- 正在啟動 Circus 來管理後端服務 ---")
        circus_cmd = [sys.executable, "-m", "circus.circusd", "config/circus.ini"]
        circus_proc = subprocess.Popen(circus_cmd, text=True, encoding='utf-8')
        log.info(f"✅ Circusd 已啟動 (PID: {circus_proc.pid})。")

        # 步驟 3: 等待 API 伺服器就緒
        log.info("--- 正在等待 API 伺服器就緒 ---")
        api_port = 42649 # 從 circus.ini 得知
        api_health_url = f"http://127.0.0.1:{api_port}/api/health"
        timeout = time.time() + 45 # 45 秒超時
        server_ready = False
        while time.time() < timeout:
            try:
                response = requests.get(api_health_url)
                if response.status_code == 200:
                    log.info("✅ API 伺服器健康檢查通過。")
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1) # 伺服器尚未啟動，稍後重試

        if not server_ready:
            raise RuntimeError(f"等待 API 伺服器在 {api_health_url} 上就緒超時。")
        log.info(f"✅ 所有背景服務已準備就緒。")

        # 步驟 4: 執行 Pytest
        log.info("--- 正在執行 pytest ---")
        # 將命令列參數 (除了腳本名稱本身) 傳遞給 pytest
        pytest_args = sys.argv[1:]

        # 為了處理既有的損壞測試，我們明確地忽略它們
        # 這確保了我們可以驗證測試執行器本身的功能
        ignore_args = []
        for arg in ignore_args:
            if arg not in pytest_args:
                pytest_args.insert(0, arg)

        log.info(f"傳遞給 pytest 的參數: {pytest_args}")
        # 使用 pytest.ExitCode.OK 來進行比較，更具可讀性
        exit_code = pytest.main(pytest_args)

        # Pytest 的一些結束代碼 (如 5) 表示沒有收集到測試，這在某些情況下是正常的
        if exit_code not in [pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED]:
            log.error(f"Pytest 以結束代碼 {exit_code} 結束，表示有測試失敗。")
        else:
            log.info("✅ 所有測試皆通過。")

    finally:
        log.info("--- 正在準備關閉服務 (Teardown) ---")
        if circus_proc:
            try:
                log.info("正在透過 circusctl 優雅地關閉所有服務...")
                subprocess.check_call([sys.executable, "-m", "circus.circusctl", "quit"])
                # 等待 circusd 程序結束
                circus_proc.wait(timeout=15)
                log.info("✅ 所有服務已成功關閉。")
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
                log.error(f"⚠️ 無法優雅地關閉 circus ({e})。將執行強制清理。")
                cleanup_stale_processes()

        log.info("🏁 測試啟動器執行完畢。")
        # 以 pytest 的結束代碼退出，以便 CI/CD 系統可以正確判斷狀態
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
