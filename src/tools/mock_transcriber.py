# tools/mock_transcriber.py

# --- 可供 bake_envs.py 解析的依賴定義 ---
# 這個工具沒有任何依賴
DEPENDENCIES = {}

import time
import logging
import argparse
from pathlib import Path
import json
import sys

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('mock_transcriber_tool')

def do_mock_transcription(output_file_path: str):
    """
    執行模擬轉錄，並將逐句結果以 JSON 格式輸出到 stdout。
    """
    log.info("(模擬) 開始處理轉錄任務...")
    time.sleep(0.5) # 模擬模型載入

    mock_sentences = [
        "你好，", "歡迎使用鳳凰音訊轉錄儀。", "這是一個模擬的轉錄過程。",
        "我們正在逐句產生文字。", "這個功能將會帶來更好的使用者體驗。", "轉錄即將完成。"
    ]

    full_transcript = []
    for i, sentence in enumerate(mock_sentences):
        # 模擬真實 transcriber 的輸出格式
        segment_data = {
            "type": "segment",
            "start": i * 2.0,
            "end": i * 2.0 + 1.8,
            "text": sentence.strip()
        }
        print(json.dumps(segment_data, ensure_ascii=False), flush=True)
        full_transcript.append(sentence)
        time.sleep(0.2) # 模擬轉錄延遲

    # 模擬最終的統計資訊
    final_data = {
        "type": "final",
        "audio_duration": 12.5,
        "processing_time": sum([0.5, 0.2 * len(mock_sentences)])
    }
    print(json.dumps(final_data), flush=True)

    # 為了相容性，仍然將完整結果寫入檔案
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(full_transcript), encoding='utf-8')
    log.info(f"✅ (模擬) 成功將最終結果寫入到: {output_file_path}")


def main():
    """
    主函數，解析命令列參數並根據 command 執行不同操作。
    使其介面與 tools/transcriber.py 相容。
    """
    parser = argparse.ArgumentParser(description="一個與真實轉錄器介面相容的模擬工具。")
    parser.add_argument("--command", type=str, default="transcribe", choices=["transcribe", "check", "download"], help="要執行的操作。")
    # 轉錄參數
    parser.add_argument("--audio_file", type=str, help="[transcribe] 需要轉錄的音訊檔案路徑。")
    parser.add_argument("--output_file", type=str, help="[transcribe] 儲存轉錄結果的檔案路徑。")
    parser.add_argument("--language", type=str, default=None, help="[transcribe] 音訊的語言 (被忽略)。")
    parser.add_argument("--beam_size", type=int, default=5, help="[transcribe] 解碼時使用的光束大小 (被忽略)。")
    # 通用參數
    parser.add_argument("--model_size", type=str, default="tiny", help="要使用/檢查/下載的模型大小 (被忽略)。")

    args = parser.parse_args()

    log.info(f"🚀 (模擬) 工具啟動，命令: '{args.command}'，參數: {args}")

    if args.command == "check":
        # 在模擬模式下，我們假設任何模型都「存在」，以避免觸發下載
        print("exists")
        log.info(f"(模擬) 檢查模型 '{args.model_size}'，回傳 'exists'。")
        return

    if args.command == "download":
        # 模擬一個快速的成功下載
        log.info(f"(模擬) 開始下載模型 '{args.model_size}'...")
        time.sleep(1)
        print(json.dumps({"progress": 100, "log": "模型下載完成 (模擬)"}), flush=True)
        log.info(f"(模擬) 模型 '{args.model_size}' 下載完成。")
        return

    # --- 預設為轉錄 ---
    if not args.audio_file or not args.output_file:
        parser.error("--audio_file 和 --output_file 是 'transcribe' 命令的必要參數。")

    try:
        do_mock_transcription(args.output_file)
    except Exception as e:
        log.critical(f"❌ (模擬) 在執行過程中發生致命錯誤: {e}", exc_info=True)
        error_file = Path(args.output_file).parent / f"{Path(args.output_file).stem}.error"
        error_file.write_text(str(e), encoding='utf-8')
        exit(1)

if __name__ == "__main__":
    main()
