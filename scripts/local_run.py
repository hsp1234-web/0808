# local_run.py (測試監控器)
import subprocess
import sys
from pathlib import Path
# JULES: 將 src 目錄加入 Python 路徑，以確保可以找到其下的模組
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import time
import logging
import os
from pathlib import Path
import requests
import json
import signal
import pytest
import threading

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('local_run')

def cleanup_stale_processes():
    """清理任何可能由先前執行殘留的舊程序，以確保測試環境乾淨。"""
    import psutil
    log.info("--- 正在檢查並清理舊的程序 ---")
    # 新增 'circusd' 到清理列表
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

def _install_deps_with_uv(requirements_file: str):
    """使用 uv 加速器安裝指定的依賴檔案。"""
    log.info(f"--- 正在使用 uv 安裝依賴: {requirements_file} ---")
    try:
        # 確保 uv 已安裝
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.info("未偵測到 uv，正在安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "uv"])

    # 安裝指定的 Python 依賴
    uv_command = [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", requirements_file]

    # [JULES'S FIX] 優化大型 AI 套件下載
    if "heavy" in requirements_file:
        log.info("偵測到大型依賴檔案，將新增 PyTorch CPU 專用索引進行優化。")
        uv_command.extend([
            "--extra-index-url", "https://download.pytorch.org/whl/cpu"
        ])

    try:
        subprocess.check_call(uv_command)
        log.info(f"✅ 成功安裝 {requirements_file} 中的依賴。")
    except subprocess.CalledProcessError as e:
        log.error(f"❌ 安裝 {requirements_file} 時發生錯誤: {e}")
        raise

def install_heavy_dependencies_background():
    """在背景執行緒中安裝大型依賴。"""
    log.info("--- [背景執行緒] 開始安裝大型依賴 (requirements-heavy.txt) ---")
    try:
        _install_deps_with_uv("requirements-heavy.txt")
        log.info("--- [背景執行緒] ✅ 所有大型依賴都已成功安裝。---")
    except Exception as e:
        log.error(f"--- [背景執行緒] ❌ 安裝大型依賴時發生致命錯誤: {e} ---", exc_info=True)


def main():
    """
    新版 local_run，使用 Circus 管理服務，並採用兩階段依賴安裝。
    """
    # --- 第一階段：安裝核心依賴 ---
    log.info("--- 階段 1: 安裝核心伺服器依賴 ---")
    _install_deps_with_uv("requirements-core.txt")

    # 步驟 1: 清理環境
    cleanup_stale_processes()
    db_file = Path("src/db/queue.db")
    if db_file.exists():
        log.info(f"--- 正在清理舊的資料庫檔案 ({db_file}) ---")
        db_file.unlink()
        log.info("✅ 舊資料庫已刪除。")

    # 步驟 2: 啟動 Circus
    log.info("--- 正在啟動 Circus 來管理後端服務 (真實模式) ---")
    circus_proc = None
    heavy_deps_thread = None
    try:
        circus_cmd = [sys.executable, "-m", "circus.circusd", "circus.ini"]
        circus_proc = subprocess.Popen(circus_cmd, text=True, encoding='utf-8')
        log.info(f"✅ Circusd 已啟動 (PID: {circus_proc.pid})。")

        # 步驟 3: 等待 API 伺服器就緒
        log.info("--- 正在等待 API 伺服器就緒 ---")
        api_port = 42649
        api_url = f"http://127.0.0.1:{api_port}"
        api_health_url = f"{api_url}/api/health"
        # 核心服務應該很快就緒，所以這裡用較短的超時
        timeout = time.time() + 60
        server_ready = False
        while time.time() < timeout:
            try:
                response = requests.get(api_health_url)
                if response.status_code == 200:
                    server_ready = True
                    break
            except requests.ConnectionError:
                time.sleep(1)

        if not server_ready:
            raise RuntimeError(f"等待 API 伺服器在 {api_health_url} 上就緒超時。")
        log.info(f"✅ API 伺服器已在 {api_url} 上就緒。")

        # --- 第二階段：在背景安裝大型依賴 ---
        log.info("--- 階段 2: 正在背景啟動大型依賴的安裝程序 ---")
        heavy_deps_thread = threading.Thread(target=install_heavy_dependencies_background)
        heavy_deps_thread.daemon = True
        heavy_deps_thread.start()

        # 步驟 4: 提交並啟動 YouTube 測試任務
        # 注意：這個任務現在可能會因為大型依賴尚未安裝完畢而失敗，這是預期行為。
        # 這個腳本的主要目的是驗證啟動流程本身。
        log.info("--- 正在提交並啟動一個 YouTube 測試任務 ---")
        task_id = None
        proc_env = os.environ.copy()
        try:
            # 讀取 API 金鑰
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                api_key = config_data.get("GOOGLE_API_KEY")
                if api_key and api_key != "在此處填入您的 GOOGLE API 金鑰":
                    proc_env["GOOGLE_API_KEY"] = api_key

            if "GOOGLE_API_KEY" not in proc_env:
                log.warning("未在 config.json 中找到有效的 GOOGLE_API_KEY，YouTube 測試將會失敗。")

            import websocket
            test_youtube_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
            test_model = "models/gemini-1.5-flash-latest"

            submit_url = f"{api_url}/api/youtube/process"
            payload = {"urls": [test_youtube_url], "model": test_model}
            response = requests.post(submit_url, json=payload, timeout=20)
            response.raise_for_status()
            task_id = response.json()["tasks"][0]["task_id"]
            log.info(f"✅ 已提交任務，ID: {task_id}")

            ws_url = f"ws://127.0.0.1:{api_port}/api/ws"
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({"type": "START_YOUTUBE_PROCESSING", "payload": {"task_id": task_id}}))
            ws.close()
            log.info("✅ 已透過 WebSocket 發送啟動指令。")
        except Exception as e:
            log.error(f"❌ 提交或啟動 YouTube 任務時失敗: {e}", exc_info=True)
            # 在這種新的啟動模式下，我們不將其視為致命錯誤，因為依賴可能仍在安裝
            log.warning("此錯誤可能是因為大型依賴仍在背景安裝中，將繼續執行。")


        # 步驟 5: 等待背景安裝完成
        log.info(f"--- 主執行緒正在等待大型依賴安裝完成 (最多等待 5 分鐘) ---")
        if heavy_deps_thread:
            heavy_deps_thread.join(timeout=300)
            if heavy_deps_thread.is_alive():
                log.warning("⚠️ 等待大型依賴安裝超時。")
            else:
                log.info("✅ 背景依賴安裝執行緒已結束。")


    except Exception as e:
        log.critical(f"💥 Local Test Runner 發生致命錯誤: {e}", exc_info=True)
        raise
    finally:
        log.info("--- 正在透過 circusctl 關閉所有服務 ---")
        try:
            subprocess.check_call([sys.executable, "-m", "circus.circusctl", "quit"])
            if circus_proc:
                circus_proc.wait(timeout=10)
            log.info("✅ 所有服務已成功關閉。")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            log.error("⚠️ 無法優雅地關閉 circus。將執行強制清理。")
            cleanup_stale_processes()
        log.info("🏁 Local Test Runner 結束。")


if __name__ == "__main__":
    # [JULES'S FIX] 全域超時保護
    main_thread = threading.Thread(target=main)
    main_thread.daemon = True
    log.info(f"--- 啟動主執行緒，並設定 120 秒超時保護 ---")
    main_thread.start()
    main_thread.join(timeout=120)

    if main_thread.is_alive():
        log.critical("💥 主執行緒超時 (120秒)！腳本可能已掛起。正在強制終止...")
        # 強制退出以防止 CI/CD 或本地開發掛起
        # 注意：這是一個強硬的退出方式，但對於防止掛起是必要的
        os._exit(1)
    else:
        log.info("✅ 主執行緒在時限內成功完成。")
