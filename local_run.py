# local_run.py (測試監控器)
import subprocess
import sys
import time
import logging
from pathlib import Path
import re

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('local_run')

def main():
    """
    專為自動化測試設計的啟動器。
    它會啟動協調器，提交一個任務，然後等待系統變回 IDLE 狀態後自動退出。
    """
    log.info("🚀 Local Test Runner: 啟動...")
    orchestrator_proc = None
    try:
        # 1. 啟動協調器 (在真實模式下)
        log.info("--- 步驟 1/4: 啟動協調器 ---")
        cmd = [sys.executable, "orchestrator.py"]
        orchestrator_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # 將 stderr 合併到 stdout
            text=True,
            encoding='utf-8'
        )
        log.info(f"✅ 協調器已啟動 (PID: {orchestrator_proc.pid})")

        # 2. 等待 API 伺服器就緒並取得埠號
        log.info("--- 步驟 2/4: 等待 API 伺服器就緒並取得埠號 ---")
        api_port = None
        port_pattern = re.compile(r"API_PORT:\s*(\d+)")
        start_time = time.time()
        timeout = 30 # 30 秒超時

        server_ready = False
        uvicorn_ready_pattern = re.compile(r"Uvicorn running on")

        for line in iter(orchestrator_proc.stdout.readline, ''):
            log.info(f"[Orchestrator]: {line.strip()}") # 顯示日誌以便除錯

            if not api_port:
                port_match = port_pattern.search(line)
                if port_match:
                    api_port = port_match.group(1)
                    log.info(f"✅ 偵測到 API 埠號: {api_port}")

            if not server_ready:
                if uvicorn_ready_pattern.search(line):
                    server_ready = True
                    log.info("✅ Uvicorn 伺服器已就緒。")

            if api_port and server_ready:
                log.info("✅ API 伺服器已完全準備就緒。")
                break

            if time.time() - start_time > timeout:
                log.error("❌ 等待 API 伺服器就緒超時。")
                raise RuntimeError("API server did not become ready in time.")

        # 檢查協調器是否仍在運行
        if orchestrator_proc.poll() is not None:
             log.error("❌ 協調器在啟動過程中意外終止。")
             log.error("--- 協調器日誌 ---")
             # 讀取剩餘的日誌
             for line in orchestrator_proc.stdout:
                 log.error(line.strip())
             return

        # 3. 提交一個測試任務
        log.info("--- 步驟 3/4: 提交一個測試任務 ---")
        try:
            import requests
            api_url = f"http://127.0.0.1:{api_port}/api/transcribe"
            log.info(f"準備提交任務至: {api_url}")

            # 建立一個假的音訊檔案用於上傳
            Path("temp_dummy_for_test.wav").write_bytes(b"dummy audio data")
            with open("temp_dummy_for_test.wav", "rb") as f:
                files = {'file': ('test.wav', f, 'audio/wav')}
                response = requests.post(api_url, files=files, timeout=10)
                response.raise_for_status()
                task_id = response.json()['task_id']
                log.info(f"✅ 成功提交任務，Task ID: {task_id}")
        except Exception as e:
            log.error(f"❌ 提交任務時失敗: {e}", exc_info=True)
            return # 提前終止
        finally:
            Path("temp_dummy_for_test.wav").unlink(missing_ok=True)


        # 4. 監聽心跳信號，直到偵測到 IDLE
        log.info("--- 步驟 4/4: 監聽心跳，等待系統變為 IDLE ---")
        running_detected = False
        idle_after_running_detected = False

        # 設定一個總體的超時，以防萬一
        timeout = time.time() + 60 # 60 秒超時

        for line in iter(orchestrator_proc.stdout.readline, ''):
            line = line.strip()
            log.info(f"[Orchestrator]: {line}") # 打印所有協調器的輸出

            if "HEARTBEAT: RUNNING" in line:
                running_detected = True
                log.info("✅ 偵測到 RUNNING 狀態。")

            if running_detected and "HEARTBEAT: IDLE" in line:
                log.info("✅ 偵測到任務完成後的 IDLE 狀態。測試成功！")
                idle_after_running_detected = True
                break # 成功，跳出迴圈

            if time.time() > timeout:
                log.error("❌ 測試超時！系統未在指定時間內變回 IDLE。")
                break

        if not idle_after_running_detected:
            log.error("❌ 測試流程結束，但未偵測到預期的『RUNNING -> IDLE』狀態轉換。")

    except Exception as e:
        log.critical(f"💥 Local Test Runner 發生致命錯誤: {e}", exc_info=True)
    finally:
        if orchestrator_proc and orchestrator_proc.poll() is None:
            log.info("--- 正在終止協調器 ---")
            orchestrator_proc.terminate()
            orchestrator_proc.wait(timeout=5)
        log.info("🏁 Local Test Runner 結束。")

if __name__ == "__main__":
    main()
