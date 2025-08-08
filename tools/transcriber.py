# tools/transcriber.py

# --- 可供 bake_envs.py 解析的依賴定義 ---
# 使用 ast.literal_eval 安全解析
DEPENDENCIES = {
    # '套件名': '在 pip install 中使用的名稱'
    'faster-whisper': 'faster-whisper',
    'opencc': 'opencc-python-reimplemented'
}

import time
import logging
import argparse
from pathlib import Path
from opencc import OpenCC

# --- 日誌設定 ---
# 設定一個基本的日誌記錄器，以便在工具執行時提供有用的輸出
# 這對於在背景執行時進行偵錯至關重要
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # 直接輸出到 stderr
    ]
)
log = logging.getLogger('transcriber_tool')

class Transcriber:
    """
    一個獨立的轉錄工具類別。
    它在初始化時載入指定的 faster-whisper 模型，並提供一個方法來執行轉錄。
    這個版本被簡化了，移除了單例模式和多模型快取，因為它被設計為在
    一個隔離的、一次性的「預烘烤」環境中運行。
    """
    def __init__(self, model_size: str):
        """
        在實例化時直接載入模型。
        """
        self.model_size = model_size
        self.model = self._load_model()

    def _load_model(self):
        """
        根據指定的模型大小載入 faster-whisper 模型。
        """
        log.info(f"🧠 開始載入 '{self.model_size}' 模型...")
        start_time = time.time()
        try:
            from faster_whisper import WhisperModel
            # 在工具化執行中，我們可以假設環境是固定的，
            # 例如，總是使用 CPU。未來可以透過參數傳遞來增加彈性。
            model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            duration = time.time() - start_time
            log.info(f"✅ 成功載入 '{self.model_size}' 模型！耗時: {duration:.2f} 秒。")
            return model
        except ImportError as e:
            log.critical(f"❌ 模型載入失敗：缺少 'faster_whisper' 模組。請確認環境已正確安裝。")
            raise e
        except Exception as e:
            log.critical(f"❌ 載入 '{self.model_size}' 模型時發生未預期錯誤: {e}", exc_info=True)
            raise e

    def transcribe(self, audio_path: str, language: str) -> str:
        """
        執行音訊轉錄的核心方法。
        """
        log.info(f"🎤 開始處理轉錄任務: {audio_path}")
        if not self.model:
            log.error("❌ 模型未被載入，無法進行轉錄。")
            raise RuntimeError("模型未被載入，無法進行轉錄。")

        try:
            start_time = time.time()
            log.info("模型載入完成，開始轉錄...")

            segments, info = self.model.transcribe(audio_path, beam_size=5, language=language, word_timestamps=True)

            detected_lang_msg = f"'{info.language}' (機率: {info.language_probability:.2f})"
            if language:
                log.info(f"🌍 使用者指定語言: '{language}'，模型偵測到 {detected_lang_msg}")
            else:
                log.info(f"🌍 未指定語言，模型自動偵測到 {detected_lang_msg}")

            full_transcript = "".join(segment.text for segment in segments).strip()

            duration = time.time() - start_time
            log.info(f"📝 轉錄完成。耗時: {duration:.2f} 秒。")

            # 如果偵測到的語言是中文，則進行繁簡轉換
            if info.language.lower().startswith('zh'):
                log.info("🔄 偵測到中文，正在執行繁體化處理...")
                try:
                    cc = OpenCC('s2twp')
                    converted_transcript = cc.convert(full_transcript)
                    log.info("✅ 繁體化處理完成。")
                    return converted_transcript
                except Exception as e:
                    log.error(f"❌ 繁簡轉換時發生錯誤: {e}", exc_info=True)
                    # 轉換失敗時，回傳原始轉錄稿
                    return full_transcript
            else:
                return full_transcript

        except Exception as e:
            log.error(f"❌ 轉錄過程中發生錯誤: {e}", exc_info=True)
            raise e

def main():
    """
    主函數，用於解析命令列參數並啟動轉錄流程。
    """
    parser = argparse.ArgumentParser(description="一個獨立的音訊轉錄工具。")
    parser.add_argument("audio_file", type=str, help="需要轉錄的音訊檔案路徑。")
    parser.add_argument("output_file", type=str, help="儲存轉錄結果的檔案路徑。")
    parser.add_argument("--model_size", type=str, default="tiny", help="要使用的 Whisper 模型大小 (例如 'tiny', 'base', 'small')。")
    parser.add_argument("--language", type=str, default=None, help="音訊的語言 (例如 'en', 'zh')。如果未指定，將自動偵測。")

    args = parser.parse_args()

    log.info(f"🚀 工具啟動，參數: {args}")

    try:
        # 1. 初始化轉錄器 (這會載入模型)
        transcriber = Transcriber(model_size=args.model_size)

        # 2. 執行轉錄
        result_text = transcriber.transcribe(args.audio_file, args.language)

        # 3. 將結果寫入輸出檔案
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True) # 確保目標資料夾存在
        output_path.write_text(result_text, encoding='utf-8')

        log.info(f"✅ 成功將結果寫入到: {args.output_file}")

    except Exception as e:
        log.critical(f"❌ 在執行過程中發生致命錯誤: {e}", exc_info=True)
        # 可以在此處建立一個錯誤標記檔案，以便外部執行器知道發生了問題
        error_file = Path(args.output_file).parent / f"{Path(args.output_file).stem}.error"
        error_file.write_text(str(e), encoding='utf-8')
        exit(1) # 以非零狀態碼退出，表示失敗

if __name__ == "__main__":
    main()
