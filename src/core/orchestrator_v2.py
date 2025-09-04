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
import sys
from pathlib import Path
this_file = Path(__file__).resolve()
SRC_DIR = this_file.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db.client_v2 import get_client


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
log = logging.getLogger('orchestrator')

# --- 全域變數 ---
processes = []
threads = []
stop_event = threading.Event()
db_client = None

# --- 公用函式 ---
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def stream_reader(stream, prefix, ready_event=None, ready_signal=None, port_list=None, port_regex=None):
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
    log.info(f"🔧 正在啟動 Worker，將其指向 API Port: {api_port}...")
    worker_cmd = [sys.executable, "src/worker/worker_v2.py"]
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
        # 根據是否為模擬模式，決定執行路徑
        if args.mock:
            # --- MOCK MODE ---
            log.info("--- [協調器以 MOCK 模式啟動] ---")
            log.info("--- [MOCK] 將跳過 DB 管理器和 Worker 的啟動，直接啟動 API 伺服器。---")

            # 在 mock 模式下，使用固定的埠號以便 Playwright 連接
            api_port = args.port if args.port else 42650

            # 設定環境變數，確保 API 伺服器也以 mock 模式運行
            env = os.environ.copy()
            env["API_MODE"] = "mock"

            # 建立啟動 API 伺服器的指令
            api_server_cmd = [sys.executable, "-u", "src/api/api_server_v2.py", "--port", str(api_port)]

            # 啟動 API 伺服器
            api_proc = subprocess.Popen(api_server_cmd, stdout=sys.stdout, stderr=sys.stderr, env=env)
            processes.append(api_proc)
            log.info(f"API 伺服器程序已在 Mock 模式下啟動，PID: {api_proc.pid}，埠號: {api_port}")

            # 等待 API 伺服器程序結束
            api_proc.wait()

        else:
            # --- NORMAL MODE ---
            log.info("--- [協調器啟動 (正常模式)] ---")

            # 1. 啟動資料庫管理者
            log.info("🔧 正在啟動資料庫管理者...")
            db_manager_port_list = []
            db_manager_cmd = [sys.executable, "src/db/manager_v2.py"]
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

            start_time = time.time()
            while not db_manager_port_list:
                if time.time() - start_time > 30:
                    raise RuntimeError("等待資料庫管理者埠號超時。")
                if db_manager_proc.poll() is not None:
                    raise RuntimeError(f"資料庫管理者程序在啟動期間意外終止，返回碼: {db_manager_proc.returncode}")
                time.sleep(0.1)

            db_manager_port = db_manager_port_list[0]
            os.environ['DB_MANAGER_PORT'] = str(db_manager_port)
            log.info(f"✅ 資料庫管理者已就緒，監聽於埠號: {db_manager_port}")

            # 2. 初始化 DB 客戶端
            db_client = get_client()
            log.info("✅ DB 客戶端初始化完成。")

            # 3. 啟動 API 伺服器
            log.info("🔧 正在啟動 API 伺服器...")
            api_port = args.port if args.port else find_free_port()
            api_server_cmd = [sys.executable, "src/api/api_server_v2.py", "--port", str(api_port)]

            api_proc = subprocess.Popen(api_server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
            processes.append(api_proc)
            log.info(f"API 伺服器程序已啟動，PID: {api_proc.pid}，埠號: {api_port}")

            print(f"PROXY_URL: http://127.0.0.1:{api_port}", flush=True)

            api_stdout_thread = threading.Thread(target=stream_reader, args=(api_proc.stdout, 'api_server', None, None))
            api_stderr_thread = threading.Thread(target=stream_reader, args=(api_proc.stderr, 'api_server_stderr', None, None))
            threads.extend([api_stdout_thread, api_stderr_thread])
            for t in [api_stdout_thread, api_stderr_thread]:
                t.daemon = True
                t.start()

            # 4. 啟動並監控 Worker
            worker_proc = start_worker(args.mock, api_port, processes, threads)

            log.info("--- [協調器進入監控模式] ---")
            last_check_time = time.time()
            initial_grace_period = 60

            while not stop_event.is_set():
                if time.time() - last_check_time > 15:
                    worker_is_dead = worker_proc.poll() is not None
                    if worker_is_dead:
                        log.critical(f"🚨 [監工] 偵測到 Worker 程序 (PID: {worker_proc.pid}) 已死亡。正在重啟...")
                        processes.remove(worker_proc)
                        worker_proc = start_worker(args.mock, api_port, processes, threads)
                        log.info(f"✅ Worker 已成功重啟，新的 PID: {worker_proc.pid}")
                    # ... (rest of the monitoring logic can be added here if needed) ...
                    last_check_time = time.time()
                time.sleep(2)

    except (Exception, KeyboardInterrupt) as e:
        if isinstance(e, KeyboardInterrupt):
            log.warning("捕獲到手動中斷信號...")
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
        log.info("✅ 所有子程序與執行緒已清理完畢。")
        sys.exit(1 if 'e' in locals() and not isinstance(e, KeyboardInterrupt) else 0)


if __name__ == "__main__":
    main()
