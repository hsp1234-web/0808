# app/core/transcriber.py
import time
import threading
import logging
from pathlib import Path
from opencc import OpenCC

log = logging.getLogger('transcriber')

class Transcriber:
    """
    一個管理 Whisper 模型生命週期並執行轉錄的類別。
    實現了延遲載入 (lazy loading) 與快取機制，以確保只有在首次需要時才載入特定大小的模型，
    從而加快應用程式的初始啟動速度並在後續請求中重複使用已載入的模型。
    """
    _instance = None
    _models = {}  # 修改為字典以快取不同大小的模型
    _model_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Transcriber, cls).__new__(cls)
        return cls._instance

    def _load_model(self, model_size: str = "tiny"):
        """
        私有方法，根據指定的模型大小載入或從快取中取得 faster-whisper 模型。
        """
        # 檢查快取中是否已有此模型
        if model_size in self._models:
            log.info(f"🧠 從快取中取得 '{model_size}' 模型。")
            return self._models[model_size]

        # 如果快取中沒有，則加載新模型
        with self._model_lock:
            # 再次檢查，防止在等待鎖的過程中其他執行緒已經載入
            if model_size in self._models:
                return self._models[model_size]

            log.info(f"🧠 快取中無 '{model_size}' 模型。開始執行首次載入...")
            start_time = time.time()
            try:
                from faster_whisper import WhisperModel

                # TODO: 未來可以根據系統是否有 GPU 自動選擇 device 和 compute_type
                model = WhisperModel(model_size, device="cpu", compute_type="int8")

                duration = time.time() - start_time
                log.info(f"✅ 成功載入 '{model_size}' 模型！耗時: {duration:.2f} 秒。")

                # 將新載入的模型存入快取
                self._models[model_size] = model
                return model
            except ImportError as e:
                log.critical(f"❌ 模型載入失敗：缺少 'faster_whisper' 模組。請確認 'requirements-worker.txt' 已正確安裝。")
                raise e
            except Exception as e:
                log.critical(f"❌ 載入 '{model_size}' 模型時發生未預期錯誤: {e}", exc_info=True)
                raise e

    def transcribe(self, audio_path: Path | str, model_size: str, language: str) -> str:
        """
        執行音訊轉錄的核心方法。

        Args:
            audio_path (Path | str): 需要轉錄的音訊檔案路徑。
            model_size (str): 要使用的 Whisper 模型大小 (例如 "tiny", "small")。
            language (str): 要使用的語言代碼 (例如 "zh", "en")。

        Returns:
            str: 轉錄後的文字結果。
        """
        log.info(f"🎤 開始處理轉錄任務: {audio_path}")

        # 1. 根據指定大小載入或取得模型
        try:
            model = self._load_model(model_size)
        except Exception as e:
            return f"轉錄失敗：無法載入模型 '{model_size}'。錯誤: {e}"

        if model is None:
            return f"轉錄失敗：模型 '{model_size}' 實例不存在。"

        # 2. 執行轉錄
        try:
            start_time = time.time()
            # 將 language 參數傳遞給 faster-whisper
            segments, info = model.transcribe(str(audio_path), beam_size=5, language=language)

            # 如果使用者指定了語言，我們就相信它。如果沒有，我們記錄偵測到的語言。
            if language:
                log.info(f"🌍 使用者指定語言: '{language}'，偵測到 '{info.language}' (機率: {info.language_probability:.2f})")
            else:
                log.info(f"🌍 自動偵測到語言: '{info.language}' (機率: {info.language_probability:.2f})")

            # 將所有片段組合成一個完整的字串
            full_transcript = "".join(segment.text for segment in segments).strip()
            duration = time.time() - start_time
            log.info(f"📝 轉錄完成。耗時: {duration:.2f} 秒。")

            # 檢查是否需要進行繁簡轉換
            if language and language.lower().startswith('zh'):
                log.info("🔄 偵測到中文，正在執行繁體化處理...")
                try:
                    cc = OpenCC('s2twp')
                    converted_transcript = cc.convert(full_transcript)
                    log.info("✅ 繁體化處理完成。")
                    return converted_transcript
                except Exception as e:
                    log.error(f"❌ 繁簡轉換時發生錯誤: {e}", exc_info=True)
                    # 即使轉換失敗，也返回原始轉錄結果，確保流程不中斷
                    return full_transcript
            else:
                return full_transcript

        except Exception as e:
            log.error(f"❌ 轉錄過程中發生錯誤: {e}", exc_info=True)
            return f"轉錄失敗：處理過程中發生錯誤。錯誤: {e}"

# 建立一個全域的單例，方便在應用的其他地方匯入和使用
transcriber_instance = Transcriber()
