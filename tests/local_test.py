# tests/local_test.py
import requests
import time
import os
import wave
import struct

# --- 組態設定 ---
BASE_URL = "http://127.0.0.1:8000"  # 假設伺服器在本機 8000 埠啟動
DUMMY_AUDIO_PATH = "dummy_test_audio.wav"

def create_dummy_wav_file(path: str, duration_s: int = 1, sample_rate: int = 16000):
    """
    產生一個用於測試的無聲 WAV 檔案。
    """
    with wave.open(path, 'w') as f:
        f.setnchannels(1)  # 單聲道
        f.setsampwidth(2)  # 16-bit
        f.setframerate(sample_rate)
        num_frames = duration_s * sample_rate
        for _ in range(num_frames):
            f.writeframes(struct.pack('<h', 0)) # 寫入靜音樣本
    print(f"✅ 成功建立測試用 WAV 檔案於: {path}")

def run_transcription_test():
    """
    執行一個完整的轉錄流程測試。
    """
    print("--- 🎬 開始端對端轉錄測試 ---")
    create_dummy_wav_file(DUMMY_AUDIO_PATH)

    try:
        # --- 步驟 2: 檢查伺服器健康狀態 ---
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=5)
            response.raise_for_status()
            print(f"✅ 伺服器健康檢查通過 (狀態: {response.status_code})")
        except requests.RequestException as e:
            print(f"❌ 無法連線到伺服器: {e}")
            print("   請確認您已經在另一個終端機中執行 `python scripts/local_run.py` 來啟動伺服器。")
            return False

        # --- 步驟 3: 上傳檔案並開始轉錄 ---
        task_id = None
        try:
            with open(DUMMY_AUDIO_PATH, 'rb') as f:
                files = {'file': (os.path.basename(DUMMY_AUDIO_PATH), f, 'audio/wav')}
                payload = {'model_size': 'tiny', 'language': 'en'} # 使用最小的模型以加快測試速度
                print("🚀 正在上傳檔案並提交轉錄任務...")
                response = requests.post(f"{BASE_URL}/api/transcribe", files=files, data=payload, timeout=10)
                response.raise_for_status()
                task_id = response.json().get("task_id")
                if not task_id:
                    raise ValueError("API 回應中未包含 task_id")
                print(f"✅ 任務提交成功，獲得 Task ID: {task_id}")
        except requests.RequestException as e:
            print(f"❌ 提交轉錄任務失敗: {e}")
            return False
        except (ValueError, KeyError) as e:
            print(f"❌ 解析任務提交回應時出錯: {e}")
            return False

        # --- 步驟 4: 輪詢任務狀態直到完成 ---
        start_time = time.time()
        timeout_seconds = 120 # 設定一個合理的超時時間 (2分鐘)
        final_status = None

        while time.time() - start_time < timeout_seconds:
            try:
                print(f"🔄 正在查詢任務狀態 (Task ID: {task_id})...")
                response = requests.get(f"{BASE_URL}/api/status/{task_id}", timeout=5)
                response.raise_for_status()
                status_data = response.json()
                current_status = status_data.get("status")
                detail = status_data.get("detail", "")
                print(f"   狀態: {current_status}, 詳細資訊: {detail}")

                if current_status in ["complete", "error"]:
                    final_status = current_status
                    print(f"🏁 任務結束，最終狀態為: {final_status}")
                    if final_status == 'complete':
                        print("   轉錄結果:", status_data.get("result", "[無結果]"))
                    break

                time.sleep(5) # 每 5 秒輪詢一次
            except requests.RequestException as e:
                print(f"⚠️ 輪詢狀態時發生錯誤: {e}。將在 5 秒後重試...")
                time.sleep(5)

        # --- 步驟 5: 驗證結果 ---
        if final_status == "complete":
            print("✅ 測試成功！轉錄任務已成功完成。")
            return True
        elif final_status == "error":
            print("❌ 測試失敗。任務以 'error' 狀態結束。")
            return False
        else:
            print(f"❌ 測試超時！在 {timeout_seconds} 秒後任務仍未完成。")
            return False

    finally:
        # --- 步驟 6: 清理 ---
        if os.path.exists(DUMMY_AUDIO_PATH):
            os.remove(DUMMY_AUDIO_PATH)
            print(f"🧹 已刪除測試檔案: {DUMMY_AUDIO_PATH}")


if __name__ == "__main__":
    if run_transcription_test():
        print("\n🎉 端對端測試通過！🎉")
        # 正常結束
        exit(0)
    else:
        print("\n🔥 端對端測試失敗。🔥")
        # 以非零狀態碼退出，表示失敗
        exit(1)
