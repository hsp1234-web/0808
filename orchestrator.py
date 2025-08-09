# orchestrator.py
import time
import subprocess
import sys
import logging
import argparse
from pathlib import Path

# 將專案根目錄加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db import database

# --- 日誌設定 ---
# 使用 stdout，以便外部程序可以捕捉心跳信號
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('orchestrator')

def main():
    """
    系統的「大腦」，負責啟動、監控所有服務，並發送心跳。
    """
    parser = argparse.ArgumentParser(description="系統協調器。")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="如果設置，則 worker 將以模擬模式運行。"
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=5,
        help="心跳及健康檢查的間隔時間（秒）。"
    )
    args = parser.parse_args()

    log.info(f"🚀 協調器啟動。模式: {'模擬 (Mock)' if args.mock else '真實 (Real)'}")

    # 在啟動服務前，確保資料庫已初始化
    database.initialize_database()

    processes = []
    try:
        # 1. 啟動 API 伺服器
        api_server_cmd = [sys.executable, "api_server.py"]
        log.info(f"🔧 正在啟動 API 伺服器: {' '.join(api_server_cmd)}")
        api_proc = subprocess.Popen(api_server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        processes.append(api_proc)
        log.info(f"✅ API 伺服器已啟動，PID: {api_proc.pid}")

        # 2. 啟動背景工作處理器
        worker_cmd = [sys.executable, "worker.py"]
        if args.mock:
            worker_cmd.append("--mock")
        log.info(f"🔧 正在啟動 Worker: {' '.join(worker_cmd)}")
        worker_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        processes.append(worker_proc)
        log.info(f"✅ Worker 已啟動，PID: {worker_proc.pid}")

        # 3. 進入主監控與心跳迴圈
        log.info("--- [協調器進入監控模式] ---")
        while True:
            # 健康檢查
            for proc in processes:
                if proc.poll() is not None:
                    log.critical(f"💥 子程序 {proc.args[1]} (PID: {proc.pid}) 已意外終止，返回碼: {proc.returncode}")
                    log.critical("--- STDOUT DUMP ---")
                    log.critical(proc.stdout.read())
                    log.critical("--- STDERR DUMP ---")
                    log.critical(proc.stderr.read())
                    raise RuntimeError(f"子程序 {proc.args[1]} 異常退出")

            # 心跳檢查
            if database.are_tasks_active():
                print("HEARTBEAT: RUNNING", flush=True)
            else:
                print("HEARTBEAT: IDLE", flush=True)

            time.sleep(args.heartbeat_interval)

    except (KeyboardInterrupt, RuntimeError) as e:
        if isinstance(e, RuntimeError):
            log.error(f"協調器因錯誤而終止: {e}")
        else:
            log.info("\n🛑 收到中斷信號，正在優雅關閉所有服務...")

    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                log.info(f"⏳ 正在終止子程序 {proc.args[1]} (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                    log.info(f"✅ 子程序 {proc.pid} 已終止。")
                except subprocess.TimeoutExpired:
                    log.warning(f"⚠️ 子程序 {proc.pid} 未能正常終止，將強制擊殺 (kill)。")
                    proc.kill()
        log.info("👋 協調器已關閉。")


if __name__ == "__main__":
    main()
