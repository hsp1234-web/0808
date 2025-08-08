# scripts/run_e2e_test.py
import requests
import time
import os
import wave
import argparse
import sys
import subprocess
import socket

# --- 常數設定 ---
HOST = "127.0.0.1"
TEST_FILENAME = "e2e_test_silent.wav"
POLL_INTERVAL_SECONDS = 1
MAX_POLL_ATTEMPTS = 60

def wait_for_server_ready(port: int, timeout: int = 30) -> bool:
    """等待伺服器就緒，直到可以建立連線。"""
    print(f"⏳ 正在等待模擬伺服器在埠號 {port} 上就緒...")
    start_time = time.monotonic()
    while time.monotonic() - start_time < timeout:
        try:
            with socket.create_connection((HOST, port), timeout=1):
                print("✅ 模擬伺服器已就緒！")
                return True
        except (socket.timeout, ConnectionRefusedError):
            time.sleep(0.5)
    print(f"❌ 等待模擬伺服器就緒超時 ({timeout}秒)。")
    return False

def generate_silent_wav(filename: str, duration: int = 1):
    """產生一個短暫的、無聲的 WAV 檔案，用於測試。"""
    print(f"🔧 正在產生測試用音訊檔: {filename}...")
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00' * (16000 * duration * 1 * 2))
    print(f"✅ 成功產生音訊檔。")

def run_test_logic(port: int):
    """執行端對端測試的核心邏輯。"""
    base_url = f"http://{HOST}:{port}"
    file_path = TEST_FILENAME
    try:
        generate_silent_wav(file_path)
        print(f"📤 正在上傳檔案至 {base_url}/api/transcribe...")
        with open(file_path, 'rb') as f:
            form_data = {"model_size": "tiny", "language": "zh"}
            files = {'file': (os.path.basename(file_path), f, 'audio/wav')}
            response = requests.post(f"{base_url}/api/transcribe", files=files, data=form_data, timeout=10)

        if response.status_code != 202:
            print(f"❌ 測試失敗：上傳檔案時 API 回應了非預期的狀態碼 {response.status_code}")
            return False

        task_id = response.json().get("task_id")
        print(f"✅ 成功提交任務，任務 ID: {task_id}")

        print(f"🔄 正在輪詢任務狀態...")
        for i in range(MAX_POLL_ATTEMPTS):
            status_response = requests.get(f"{base_url}/api/status/{task_id}", timeout=5)
            status_data = status_response.json()
            current_status = status_data.get("status")
            print(f"   嘗試 {i+1}/{MAX_POLL_ATTEMPTS}: 目前狀態是 '{current_status}' (Detail: {status_data.get('detail')})")

            if current_status == "complete":
                print("✅ 任務完成！")
                result = status_data.get("result", "")
                mock_prefix = "這是一個來自模擬轉錄器的測試結果"
                if result.startswith(mock_prefix):
                    print(f"✅ (模擬模式) 測試通過！轉錄結果符合預期。")
                    return True
                else:
                    print(f"❌ (模擬模式) 測試失敗：轉錄結果非預期。")
                    return False
            elif current_status == "error":
                print(f"❌ 測試失敗：任務回報錯誤: {status_data.get('result')}")
                return False
            time.sleep(POLL_INTERVAL_SECONDS)
        print(f"❌ 測試失敗：輪詢超時。")
        return False
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ 已成功刪除測試檔案: {file_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="啟動模擬伺服器並執行端對端 API 測試。")
    parser.add_argument("--port", type=int, default=8000, help="伺服器運行的埠號。")
    args = parser.parse_args()

    server_process = None
    try:
        # 1. 啟動模擬伺服器作為子進程
        print("\n" + "="*50)
        print("🚀 正在啟動模擬伺服器...")
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mock_server_script = os.path.join(project_root, "scripts", "run_mock_server.py")
        server_process = subprocess.Popen(
            [sys.executable, mock_server_script, "--port", str(args.port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
        )

        # 2. 等待伺服器就緒
        if not wait_for_server_ready(args.port):
            raise RuntimeError("模擬伺服器未能成功啟動。")

        # 3. 執行測試邏輯
        print("\n" + "="*50)
        print("🚀 開始執行端對端 API 測試...")
        success = run_test_logic(args.port)

    except Exception as e:
        print(f"❌ 測試過程中發生未預期的錯誤: {e}")
        success = False
    finally:
        # 4. 無論如何都確保終止伺服器子進程
        if server_process:
            print("\n" + "="*50)
            print("🛑 正在關閉模擬伺服器...")
            server_process.terminate()
            try:
                # 等待一小段時間讓它終止
                server_process.wait(timeout=5)
                print("✅ 模擬伺服器已成功關閉。")
            except subprocess.TimeoutExpired:
                print("⚠️ 伺服器未能及時終止，將強制終止。")
                server_process.kill()
                print("✅ 模擬伺服器已被強制終止。")

        # 5. 根據測試結果設定退出碼
        print("\n" + "="*50)
        if success:
            print("🎉 端對端測試成功通過！🎉")
            sys.exit(0)
        else:
            print("🔥 端對端測試失敗。🔥")
            sys.exit(1)
