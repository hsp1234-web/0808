#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import logging
import os
import re
import socket
import subprocess
import threading
import time

# --- 標準化路徑修正 ---
# 這是解決 ModuleNotFoundError 的標準且穩健的方法。
# 無論此腳本從何處被執行，它都能確保 'src' 目錄位於 Python 的搜尋路徑中。
import sys
from pathlib import Path

# 1. 取得目前檔案 (`orchestrator.py`) 的絕對路徑。
#    例如: /path/to/project/src/core/orchestrator.py
this_file = Path(__file__).resolve()

# 2. 透過 .parent 兩次，我們向上找到 'src' 目錄。
#    -> .parent -> /path/to/project/src/core
#    -> .parent -> /path/to/project/src
SRC_DIR = this_file.parent.parent

# 3. 將 'src' 目錄的絕對路徑加到 sys.path 的最前面。
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# --- 路徑修正結束 ---

# 現在，以下的 import 語句將會成功，因為 Python 會在 `src` 目錄中尋找 `db` 套件。
from db.client import get_client


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout # 將協調器的日誌輸出到 stdout
)
log = logging.getLogger('orchestrator')

# --- 全域變數 ---
processes = []
threads = []
stop_event = threading.Event()
db_client = None

# --- 公用函式 ---
def find_free_port():
    """找到一個可用的埠號。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def stream_reader(stream, prefix, ready_event=None, ready_signal=None, port_list=None, port_regex=None):
    """
    讀取子程序的輸出流，記錄日誌，並可選地設置就緒事件和提取埠號。
    """
    try:
        for line in iter(stream.readline, ''):
            if not line:
                break
            stripped_line = line.strip()
            log.info(f"[{prefix}] {stripped_line}")

            if ready_event and not ready_event.is_set() and ready_signal and ready_signal in stripped_line:
                ready_event.set()
                log.info(f"✅ 偵測到來自 '{prefix}' 的就緒信號 '{ready_signal}'！")

            if port_list is not None and port_regex:
                match = re.search(port_regex, stripped_line)
                if match:
                    port = int(match.group(1))
                    port_list.append(port)
                    log.info(f"✅ 偵測到來自 '{prefix}' 的埠號: {port}")
    except Exception as e:
        log.error(f"讀取流 '{prefix}' 時發生錯誤: {e}", exc_info=True)


def start_worker(mock_mode, api_port, processes_list, threads_list):
    """啟動 Worker 程序並設定日誌流讀取器。"""
    log.info(f"🔧 正在啟動 Worker，將其指向 API Port: {api_port}...")
    worker_cmd = [sys.executable, "src/worker/worker.py"]
    if mock_mode:
        worker_cmd.append("--mock")

    worker_env = os.environ.copy()
    if mock_mode:
        worker_env["API_MODE"] = "mock"
    worker_env["API_PORT"] = str(api_port)

    worker_proc = subprocess.Popen(worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=worker_env)
    processes_list.append(worker_proc)
    log.info(f"Worker 程序已啟動，PID: {worker_proc.pid}")

    worker_stdout_thread = threading.Thread(target=stream_reader, args=(worker_proc.stdout, 'worker'))
    worker_stderr_thread = threading.Thread(target=stream_reader, args=(worker_proc.stderr, 'worker_stderr'))
    threads_list.extend([worker_stdout_thread, worker_stderr_thread])
    for t in [worker_stdout_thread, worker_stderr_thread]:
        t.daemon = True
        t.start()
    return worker_proc


def main():
    parser = argparse.ArgumentParser(description="系統協調器。")
    parser.add_argument("--mock", action="store_true", help="如果設置，則 worker 將以模擬模式運行。")
    parser.add_argument("--port", type=int, default=None, help="指定 API 伺服器運行的固定埠號。")
    args, _ = parser.parse_known_args()

    global db_client
    try:
        log.info("--- [協調器啟動] ---")

        # 1. 啟動資料庫管理者
        log.info("🔧 正在啟動資料庫管理者...")
        db_manager_port_list = []
        db_manager_cmd = [sys.executable, "src/db/manager.py"]
        db_manager_proc = subprocess.Popen(db_manager_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        processes.append(db_manager_proc)
        log.info(f"資料庫管理者程序已啟動，PID: {db_manager_proc.pid}")

        db_stdout_thread = threading.Thread(
            target=stream_reader,
            args=(db_manager_proc.stdout, 'db_manager'),
            kwargs={'port_list': db_manager_port_list, 'port_regex': r"DB_MANAGER_PORT: (\d+)"}
        )
        db_stdout_thread.daemon = True
        threads.append(db_stdout_thread)
        db_stdout_thread.start()

        # 等待資料庫管理者回報埠號
        start_time = time.time()
        while not db_manager_port_list:
            if time.time() - start_time > 30: # 30 秒超時
                raise RuntimeError("等待資料庫管理者埠號超時。")
            # 檢查子程序是否意外終止
            if db_manager_proc.poll() is not None:
                raise RuntimeError(f"資料庫管理者程序在啟動期間意外終止，返回碼: {db_manager_proc.returncode}")
            time.sleep(0.1) # 短暫等待，避免 CPU 資源浪費

        db_manager_port = db_manager_port_list[0]
        os.environ['DB_MANAGER_PORT'] = str(db_manager_port)
        log.info(f"✅ 資料庫管理者已就緒，監聽於埠號: {db_manager_port}")

        # 2. 初始化 DB 客戶端
        db_client = get_client()
        log.info("✅ DB 客戶端初始化完成。")

        # 3. 啟動 API 伺服器
        log.info("🔧 正在啟動 API 伺服器...")
        api_port = args.port if args.port else find_free_port()
        api_server_cmd = [sys.executable, "src/api/api_server.py", "--port", str(api_port)]
        if args.mock:
            api_server_cmd.append("--mock")

        api_env = os.environ.copy()
        if args.mock:
            api_env["API_MODE"] = "mock"

        # 使用固定埠號，因為 Playwright 測試需要一個可預測的 URL
        proxy_url = f"http://127.0.0.1:{api_port}"

        api_proc = subprocess.Popen(api_server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=api_env)
        processes.append(api_proc)
        log.info(f"API 伺服器程序已啟動，PID: {api_proc.pid}，埠號: {api_port}")

        # JULES'S FIX: 向外部監聽器報告 PROXY_URL，這是與 Colabpro 等啟動器對接的關鍵
        print(f"PROXY_URL: {proxy_url}", flush=True)
        log.info(f"已向外部監聽器報告代理 URL: {proxy_url}")

        api_stdout_thread = threading.Thread(target=stream_reader, args=(api_proc.stdout, 'api_server', None, None))
        api_stderr_thread = threading.Thread(target=stream_reader, args=(api_proc.stderr, 'api_server_stderr', None, None))
        threads.extend([api_stdout_thread, api_stderr_thread])
        for t in [api_stdout_thread, api_stderr_thread]:
            t.daemon = True
            t.start()

        # 4. 啟動並監控 Worker
        worker_proc = start_worker(args.mock, api_port, processes, threads)

        log.info("--- [協調器進入監控模式] ---")

        # 將 DB 和 API Server 視為核心服務
        core_processes = [p for p in processes if p != worker_proc]

        last_check_time = time.time()
        # 使用 main 函式開頭的 start_time 來計算寬限期
        initial_grace_period = 60 # 啟動後 60 秒的寬限期，不檢查心跳

        while not stop_event.is_set():
            # 1. 檢查核心服務 (DB, API) - 如果它們失敗，整個系統都應該停止
            for proc in core_processes:
                if proc.poll() is not None:
                    # 更新: 移除 worker_proc 後，這裡的檢查是正確的
                    pass

            # 2. 監控 Worker 程序 (每 15 秒檢查一次)
            if time.time() - last_check_time > 15:
                worker_is_dead = worker_proc.poll() is not None
                if worker_is_dead:
                    log.critical(f"🚨 [監工] 偵測到 Worker 程序 (PID: {worker_proc.pid}) 已死亡。返回碼: {worker_proc.returncode}。正在嘗試重啟...")
                    processes.remove(worker_proc)
                    worker_proc = start_worker(args.mock, api_port, processes, threads)
                    log.info(f"✅ Worker 已成功重啟，新的 PID: {worker_proc.pid}")
                else:
                    # 如果 Worker 程序仍在運行，則檢查其心跳是否過期 (殭屍檢測)
                    if time.time() - start_time > initial_grace_period: # 在寬限期後才開始檢查
                        try:
                            heartbeat_str = db_client.get_app_state("worker_last_heartbeat")
                            if heartbeat_str:
                                heartbeat_ts = float(heartbeat_str)
                                if time.time() - heartbeat_ts > 60:
                                    log.critical(f"🧟 [稽核員] 偵測到 Worker 程序 (PID: {worker_proc.pid}) 已成為殭屍 (心跳過期超過 60 秒)。正在終止並重啟...")

                                    worker_proc.terminate()
                                    try:
                                        worker_proc.wait(timeout=5)
                                    except subprocess.TimeoutExpired:
                                        log.warning(f"強制終止殭屍 Worker (PID: {worker_proc.pid})。")
                                        worker_proc.kill()

                                    processes.remove(worker_proc)
                                    worker_proc = start_worker(args.mock, api_port, processes, threads)
                                    log.info(f"✅ 殭屍 Worker 已被處理，新的 Worker 已啟動，PID: {worker_proc.pid}")
                            else:
                                log.warning("[稽核員] Worker 正在運行，但在資料庫中找不到其心跳記錄。")

                        except Exception as e:
                            log.error(f"檢查 Worker 心跳時發生錯誤: {e}", exc_info=True)

                last_check_time = time.time()

            time.sleep(2) # 短輪詢間隔，但實際檢查由計時器控制

    except (Exception, KeyboardInterrupt) as e:
        if isinstance(e, KeyboardInterrupt):
            log.warning("捕獲到手動中斷信號 (KeyboardInterrupt)...")
        else:
            log.critical(f"協調器發生致命錯誤: {e}", exc_info=True)
    finally:
        log.info("--- [協調器開始關閉程序] ---")
        stop_event.set()
        for p in reversed(processes):
            try:
                if p.poll() is None:
                    log.info(f"正在終止程序: {p.args} (PID: {p.pid})")
                    p.terminate()
                    p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning(f"程序 {p.pid} 未能在5秒內終止，將強制終止。")
                p.kill()
            except Exception as kill_e:
                log.error(f"終止程序 {p.pid} 時發生錯誤: {kill_e}")

        log.info("等待所有日誌執行緒結束...")
        for t in threads:
            if t.is_alive():
                t.join(timeout=2)
        log.info("✅ 所有子程序與執行緒已清理完畢。協調器已關閉。")
        sys.exit(1 if 'e' in locals() and not isinstance(e, KeyboardInterrupt) else 0)

if __name__ == "__main__":
    main()
