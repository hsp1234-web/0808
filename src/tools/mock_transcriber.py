# -*- coding: utf-8 -*-
import time
import logging
import argparse
import sys
import json
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
log = logging.getLogger('mock_transcriber_tool')

def main():
    """
    一個極度簡化的模擬轉錄器。
    它的唯一職責就是成功退出，以允許 api_server.py 中的父程序繼續執行任務完成的邏輯。
    """
    parser = argparse.ArgumentParser(description="一個與真實轉錄器介面相容的模擬工具。")
    parser.add_argument("--command", type=str, required=True)
    parser.add_argument("--model_size", type=str)
    parser.add_argument("--audio_file", type=str)
    parser.add_argument("--output_file", type=str)
    # 忽略所有其他參數
    args, _ = parser.parse_known_args()

    if args.command == "check":
        # 模擬模型永遠存在
        log.info(f"(模擬) 檢查模型 '{args.model_size}'，回報: 永遠存在。")
        print("exists", flush=True)
        sys.exit(0)

    elif args.command == "download":
        log.info(f"📥 (模擬) 開始下載 '{args.model_size}' 模型...")
        time.sleep(0.5) # 模擬延遲
        log.info(f"✅ (模擬) 模型 '{args.model_size}' 下載完成。")
        sys.exit(0)

    elif args.command == "transcribe":
        log.info(f"🎤 (模擬) 開始處理轉錄任務: {args.audio_file}")
        time.sleep(1) # 模擬一個快速的處理延遲

        # JULES'S FIX (2025-09-02): 模擬工具不應該有太多邏輯。
        # 它只需要建立一個空的輸出檔案並成功退出。
        # api_server.py 中的 _transcribe_in_thread 執行緒會負責處理後續的資料庫更新和 WebSocket 廣播。
        try:
            # 建立一個假的輸出檔案，內容由 api_server 控制
            # 這裡我們只建立一個帶有模擬內容的檔案以確保路徑有效
            output_path = Path(args.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # JULES'S FIX (2025-09-02): 預覽測試需要特定的文字。
            output_path.write_text("這是模擬的轉錄稿內容。", encoding='utf-8')
            log.info(f"✅ (模擬) 轉錄任務完成，已建立假檔案: {args.output_file}")
            sys.exit(0)
        except Exception as e:
            log.critical(f"❌ (模擬) 在建立假檔案時發生錯誤: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
