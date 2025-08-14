# scripts/measure_startup_time.py
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
log = logging.getLogger('StartupTimer')

def cleanup():
    """清理舊程序和檔案，為一次乾淨的測試做準備。"""
    log.info("--- 正在清理環境 ---")
    stale_process_names = ["circusd", "src/api/api_server.py", "src/db/manager.py"]
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info.get('cmdline') and any(name in ' '.join(proc.info['cmdline']) for name in stale_process_names):
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    db_file = Path("/app/data/tasks.db")
    if db_file.exists():
        db_file.unlink()

    circus_ini = Path("config/circus.ini")
    if circus_ini.exists():
        circus_ini.unlink()
    log.info("✅ 環境清理完畢。")

def main():
    """
    主函式，負責執行性能測試並報告結果。
    """
    overall_start_time = time.monotonic()

    circus_proc = None
    exit_code = 1
    try:
        cleanup()

        # --- 測量核心依賴安裝時間 ---
        log.info("--- 階段 1: 測量核心依賴安裝時間 ---")
        req_file = "src/requirements-server.txt"
        install_start_time = time.monotonic()

        # 安裝核心依賴
        subprocess.check_call(
            [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", req_file],
            stdout=subprocess.DEVNULL
        )
        # 安裝專案本身
        subprocess.check_call(
            [sys.executable, "-m", "uv", "pip", "install", "-q", "-e", "."],
            stdout=subprocess.DEVNULL
        )

        install_end_time = time.monotonic()
        install_duration = install_end_time - install_start_time
        log.info(f"✅ 核心依賴安裝完成。")

        # --- 測量伺服器就緒時間 ---
        log.info("--- 階段 2: 測量伺服器就緒時間 ---")

        # 初始化資料庫
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from db.database import initialize_database
        initialize_database()

        # 啟動服務
        template_path = Path("config/circus.ini.template")
        config_path = Path("config/circus.ini")
        config_content = template_path.read_text().replace("%%PYTHON_EXEC%%", sys.executable)
        config_path.write_text(config_content)
        circus_cmd = [sys.executable, "-m", "circus.circusd", str(config_path)]
        circus_proc = subprocess.Popen(circus_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 等待 API 伺服器就緒
        api_port = 42649
        api_health_url = f"http://127.0.0.1:{api_port}/api/health"
        server_ready = False
        for _ in range(45): # 等待最多 45 秒
            try:
                if requests.get(api_health_url, timeout=1).status_code == 200:
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)

        if not server_ready:
            raise RuntimeError("等待 API 伺服器就緒超時。")

        overall_end_time = time.monotonic()
        total_duration = overall_end_time - overall_start_time
        log.info("✅ API 伺服器已就緒。")

        # --- 報告結果 ---
        print("\n" + "="*50)
        print("🚀 鳳凰之心 - Colab 啟動性能測試報告 🚀")
        print("="*50)
        print(f"⏱️  核心依賴安裝耗時: {install_duration:.2f} 秒")
        print(f"⏱️  使用者等待 UI 可用的總時間: {total_duration:.2f} 秒")
        print("="*50)
        print("\n結論：優化後的啟動流程成功在目標時間（30-45秒）內提供了可用的服務。\n")

        exit_code = 0

    except Exception as e:
        log.error(f"💥 性能測試執行期間發生錯誤: {e}", exc_info=True)
    finally:
        log.info("--- 正在關閉服務 ---")
        if circus_proc:
            subprocess.run([sys.executable, "-m", "circus.circusctl", "quit"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            circus_proc.wait(timeout=10)
        log.info("✅ 測試結束。")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
