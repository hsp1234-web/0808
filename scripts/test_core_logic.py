# scripts/test_core_logic.py
import subprocess
import sys
import time
import logging
import os
from pathlib import Path
import requests
import psutil

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('CoreLogicTester')

def cleanup():
    """清理舊程序和檔案。"""
    log.info("--- 正在清理環境 ---")

    # 1. 清理程序
    stale_process_names = ["circusd", "src/api/api_server.py", "src/db/manager.py"]
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info.get('cmdline') and any(name in ' '.join(proc.info['cmdline']) for name in stale_process_names):
                log.warning(f"偵測到殘留程序: PID={proc.pid}。正在終止...")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 2. 清理檔案
    # 注意：根據 database.py，DB 現在位於 /content/tasks.db
    db_file = Path("/content/tasks.db")
    if db_file.exists():
        db_file.unlink()
        log.info(f"已刪除舊的資料庫檔案: {db_file}")

    circus_ini = Path("config/circus.ini")
    if circus_ini.exists():
        circus_ini.unlink()
        log.info(f"已刪除舊的 circus 設定檔: {circus_ini}")

    log.info("✅ 環境清理完畢。")

def install_core_dependencies():
    """僅安裝核心伺服器依賴，以模擬快速啟動。"""
    log.info("--- 正在安裝核心依賴 (Stage 1) ---")
    req_file = "src/requirements-server.txt"
    if not Path(req_file).exists():
        raise FileNotFoundError(f"找不到核心依賴檔案: {req_file}")

    # 使用 uv 加速安裝
    try:
        subprocess.check_call([sys.executable, "-m", "uv", "pip", "install", "-r", req_file])
        # 同時需要以可編輯模式安裝專案本身
        subprocess.check_call([sys.executable, "-m", "uv", "pip", "install", "-e", "."])
    except subprocess.CalledProcessError as e:
        log.error("核心依賴安裝失敗。")
        raise e
    log.info("✅ 核心依賴安裝成功。")

def main():
    circus_proc = None
    exit_code = 1  # 預設失敗
    try:
        cleanup()
        install_core_dependencies()

        # 確保日誌目錄存在
        Path("logs").mkdir(exist_ok=True)

        # 關鍵修復：在啟動任何服務前，由主腳本同步初始化資料庫
        log.info("--- 正在從主腳本強制初始化資料庫 ---")
        # 需要將 src 加入 sys.path 才能找到 db 模組
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from db.database import initialize_database
        initialize_database()
        log.info("✅ 主腳本資料庫初始化完成。")

        log.info("--- 正在啟動後端服務 ---")
        # 動態生成 circus.ini
        template_path = Path("config/circus.ini.template")
        config_path = Path("config/circus.ini")
        config_content = template_path.read_text().replace("%%PYTHON_EXEC%%", sys.executable)
        config_path.write_text(config_content)

        circus_cmd = [sys.executable, "-m", "circus.circusd", str(config_path)]
        circus_proc = subprocess.Popen(circus_cmd)
        log.info(f"Circusd 已啟動 (PID: {circus_proc.pid})。")

        log.info("--- 等待 API 伺服器就緒 ---")
        api_port = 42649 # 從 circus.ini.template 得知
        api_health_url = f"http://127.0.0.1:{api_port}/api/health"
        api_logs_url = f"http://127.0.0.1:{api_port}/api/logs/export"

        server_ready = False
        for _ in range(30): # 等待最多 30 秒
            try:
                if requests.get(api_health_url, timeout=2).status_code == 200:
                    log.info("✅ API 伺服器健康檢查通過。")
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)

        if not server_ready:
            raise RuntimeError("等待 API 伺服器就緒超時。")

        log.info("--- 核心驗證：檢查日誌系統是否在啟動時正常運作 ---")
        logs_response = requests.get(api_logs_url, timeout=5)
        logs_response.raise_for_status()
        logs_content = logs_response.text

        log.info("收到的日誌內容 (前500字): " + logs_content[:500] + "...")

        # 關鍵驗證點
        # 在此測試流程中，api_server 會設定資料庫日誌，我們檢查其啟動訊息
        expected_log_message = "資料庫日誌處理器設定完成"
        if expected_log_message in logs_content:
            log.info(f"✅ 驗證成功！在匯出的日誌中找到了關鍵訊息: '{expected_log_message}'")
        else:
            # 為了除錯，印出完整的日誌內容
            log.error("驗證失敗的完整日誌內容：\n" + logs_content)
            raise AssertionError(f"驗證失敗！未在日誌中找到關鍵訊息: '{expected_log_message}'")

        log.info("🎉 所有核心邏輯測試通過！🎉")
        exit_code = 0

    except Exception as e:
        log.error(f"💥 測試執行期間發生錯誤: {e}", exc_info=True)
    finally:
        log.info("--- 正在關閉服務 ---")
        if circus_proc:
            subprocess.run([sys.executable, "-m", "circus.circusctl", "quit"])
            circus_proc.wait(timeout=10)
        log.info("✅ 服務已關閉。")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
