# app/core/transcriber.py
import time
import threading
import logging
from pathlib import Path

log = logging.getLogger('transcriber')

class Transcriber:
    """
    一個管理 Whisper 模型生命週期並執行轉錄的類別。
    實現了延遲載入 (lazy loading) 模式，以確保只有在首次需要時才載入模型，
    從而加快應用程式的初始啟動速度。
    """
    _instance = None
    _model = None
    _model_lock = threading.Lock()  # 確保在多執行緒環境下載入模型的原子性

    def __new__(cls, *args, **kwargs):
        # 實現單例模式，確保整個應用中只有一個 Transcriber 實例
        if not cls._instance:
            cls._instance = super(Transcriber, cls).__new__(cls)
        return cls._instance

    def _load_model(self):
        """
        私有方法，用於載入 faster-whisper 模型。
        使用鎖來防止在多執行緒環境下重複載入。
        """
        # 使用雙重檢查鎖定模式 (Double-Checked Locking) 提高效率
        if self._model is not None:
            return

        with self._model_lock:
            if self._model is None:
                log.info("🧠 模型尚未載入。開始執行首次載入...")
                start_time = time.time()
                try:
                    # 延遲載入：只在需要時才匯入
                    from faster_whisper import WhisperModel

                    # 在此處定義模型的大小和設定
                    # 'tiny' 是一個非常小的模型，適合快速測試
                    # device='cpu' and compute_type='int8' 是為了在沒有 GPU 的環境下獲得較好的效能
                    model_size = "tiny"
                    self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    duration = time.time() - start_time
                    log.info(f"✅ 模型載入成功！耗時: {duration:.2f} 秒。")
                except ImportError as e:
                    log.critical(f"❌ 模型載入失敗：缺少 'faster_whisper' 模組。請確認 'requirements-worker.txt' 已正確安裝。")
                    log.critical(f"詳細錯誤: {e}")
                    self._model = None
                    raise e # 重新引發異常，讓呼叫者知道載入失敗
                except Exception as e:
                    log.critical(f"❌ 模型載入時發生未預期錯誤: {e}", exc_info=True)
                    # 在生產環境中，這裡應該有更完善的錯誤處理
                    self._model = None
                    raise e

    def transcribe(self, audio_path: Path | str) -> str:
        """
        執行音訊轉錄的核心方法。

        Args:
            audio_path (Path | str): 需要轉錄的音訊檔案路徑。

        Returns:
            str: 轉錄後的文字結果。
        """
        log.info(f"🎤 開始處理轉錄任務: {audio_path}")

        # 1. 確保模型已載入
        try:
            self._load_model()
        except Exception as e:
            # 錯誤已在 _load_model 中被記錄，此處直接回傳給 worker
            return f"轉錄失敗：無法載入模型。錯誤: {e}"

        if self._model is None:
            return "轉錄失敗：模型實例不存在。"

        # 2. 執行轉錄
        try:
            start_time = time.time()
            segments, info = self._model.transcribe(str(audio_path), beam_size=5)

            log.info(f"🌍 偵測到的語言: '{info.language}' (機率: {info.language_probability:.2f})")

            # 將所有片段組合成一個完整的字串
            # 'segment.text' 已經包含了處理過的文字
            full_transcript = "".join(segment.text for segment in segments).strip()

            duration = time.time() - start_time
            log.info(f"📝 轉錄完成。耗時: {duration:.2f} 秒。")

            return full_transcript
        except Exception as e:
            log.error(f"❌ 轉錄過程中發生錯誤: {e}", exc_info=True)
            return f"轉錄失敗：處理過程中發生錯誤。錯誤: {e}"

# 建立一個全域的單例，方便在應用的其他地方匯入和使用
transcriber_instance = Transcriber()
