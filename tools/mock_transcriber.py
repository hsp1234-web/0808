# tools/mock_transcriber.py

# --- 可供 bake_envs.py 解析的依賴定義 ---
# 這個工具沒有任何依賴
DEPENDENCIES = {}

import time
import logging
import argparse
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('mock_transcriber_tool')

import json
import sys

def main():
    """
    主函數，用於解析命令列參數並啟動模擬轉錄流程。
    現在會將進度以 JSON 格式打印到 stdout。
    """
    parser = argparse.ArgumentParser(description="一個獨立的、輕量級的模擬音訊轉錄工具。")
    parser.add_argument("audio_file", type=str, help="需要轉錄的音訊檔案路徑 (僅用於日誌記錄)。")
    parser.add_argument("output_file", type=str, help="儲存模擬轉錄結果的檔案路徑。")
    parser.add_argument("--model_size", type=str, default="tiny", help="模型大小 (將被忽略)。")
    parser.add_argument("--language", type=str, default=None, help="音訊的語言 (將被忽略)。")

    args = parser.parse_args()

    log.info(f"🚀 (模擬) 工具啟動，參數: {args}")

    def emit_progress(progress: int, text: str):
        """向 stdout 發送 JSON 格式的進度更新"""
        progress_data = {"progress": progress, "text": text}
        print(json.dumps(progress_data), flush=True)

    try:
        log.info("(模擬) 開始處理轉錄任務...")
        emit_progress(0, "正在初始化模型...")
        time.sleep(1)

        emit_progress(10, "模型初始化完畢，正在分析音訊...")
        time.sleep(1)

        mock_sentences = [
            "你好，", "歡迎使用鳳凰音訊轉錄儀。", "這是一個模擬的轉錄過程。",
            "我們正在逐句產生文字。", "這個功能將會帶來更好的使用者體驗。", "轉錄即將完成。"
        ]

        full_transcript = []
        for i, sentence in enumerate(mock_sentences):
            full_transcript.append(sentence)
            progress = 20 + int((i + 1) / len(mock_sentences) * 70)
            emit_progress(progress, " ".join(full_transcript))
            time.sleep(0.8)

        emit_progress(100, " ".join(full_transcript))

        # 最終結果仍然寫入檔案，以保持與舊工作流程的相容性
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(" ".join(full_transcript), encoding='utf-8')

        log.info(f"✅ (模擬) 成功將最終結果寫入到: {args.output_file}")

    except Exception as e:
        log.critical(f"❌ (模擬) 在執行過程中發生致命錯誤: {e}", exc_info=True)
        error_file = Path(args.output_file).parent / f"{Path(args.output_file).stem}.error"
        error_file.write_text(str(e), encoding='utf-8')
        exit(1)

if __name__ == "__main__":
    main()
