# scripts/run_e2e_test.py
import requests
import time
import os
import wave
import argparse
import sys

# --- 常數設定 ---
HOST = "127.0.0.1"
TEST_FILENAME = "e2e_test_silent.wav"
POLL_INTERVAL_SECONDS = 1
MAX_POLL_ATTEMPTS = 60 # 最多等待 60 秒

def generate_silent_wav(filename: str, duration: int = 1):
    """產生一個短暫的、無聲的 WAV 檔案，用於測試。"""
    print(f"🔧 正在產生測試用音訊檔: {filename}...")
    n_channels = 1
    sample_width = 2  # 16-bit
    frame_rate = 16000
    n_frames = frame_rate * duration

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(frame_rate)
        wf.writeframes(b'\x00' * n_frames * n_channels * sample_width)
    print(f"✅ 成功產生音訊檔。")

def run_test(port: int):
    """執行端對端測試的核心函式。"""
    base_url = f"http://{HOST}:{port}"
    file_path = TEST_FILENAME

    # 使用 try...finally 確保測試檔案總能被刪除
    try:
        # --- 步驟 1: 產生測試檔案 ---
        generate_silent_wav(file_path)

        # --- 步驟 2: 上傳檔案並開始轉錄 ---
        print(f"📤 正在上傳檔案至 {base_url}/api/transcribe...")
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'audio/wav')}
            response = requests.post(f"{base_url}/api/transcribe", files=files, timeout=10)

        if response.status_code != 202:
            print(f"❌ 測試失敗：上傳檔案時 API 回應了非預期的狀態碼 {response.status_code}")
            print(f"   回應內容: {response.text}")
            return False

        task_id = response.json().get("task_id")
        if not task_id:
            print(f"❌ 測試失敗：API 回應中未包含 task_id。")
            return False

        print(f"✅ 成功提交任務，任務 ID: {task_id}")

        # --- 步驟 3: 輪詢任務狀態 ---
        print(f"🔄 正在輪詢任務狀態 (每 {POLL_INTERVAL_SECONDS} 秒一次)...")
        for i in range(MAX_POLL_ATTEMPTS):
            status_response = requests.get(f"{base_url}/api/status/{task_id}", timeout=5)
            status_data = status_response.json()
            current_status = status_data.get("status")

            print(f"   嘗試 {i+1}/{MAX_POLL_ATTEMPTS}: 目前狀態是 '{current_status}'")

            if current_status == "complete":
                print("✅ 任務完成！")
                result = status_data.get("result", "")
                # 因為是靜音檔案，預期轉錄結果為空字串
                if result == "":
                    print(f"✅ 測試通過！轉錄結果符合預期 (空字串)。")
                    return True
                else:
                    print(f"❌ 測試失敗：轉錄結果非預期。")
                    print(f"   預期: '' (空字串)")
                    print(f"   實際: '{result}'")
                    return False

            elif current_status == "error":
                print(f"❌ 測試失敗：任務回報錯誤。")
                print(f"   錯誤訊息: {status_data.get('result')}")
                return False

            time.sleep(POLL_INTERVAL_SECONDS)

        print(f"❌ 測試失敗：輪詢超時 ({MAX_POLL_ATTEMPTS} 秒)。任務未能完成。")
        return False

    except requests.exceptions.ConnectionError as e:
        print(f"❌ 測試失敗：無法連接到伺服器 {base_url}。請確認伺服器正在運行。")
        print(f"   錯誤: {e}")
        return False
    except Exception as e:
        print(f"❌ 測試過程中發生未預期的錯誤: {e}")
        return False
    finally:
        # --- 步驟 4: 清理測試檔案 ---
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️ 已成功刪除測試檔案: {file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="執行端對端 API 測試。")
    parser.add_argument("--port", type=int, default=8000, help="伺服器運行的埠號。")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("🚀 開始執行端對端 API 測試...")
    print("="*50)

    success = run_test(args.port)

    print("\n" + "="*50)
    if success:
        print("🎉 端對端測試成功通過！🎉")
        sys.exit(0)
    else:
        print("🔥 端對端測試失敗。🔥")
        sys.exit(1)
