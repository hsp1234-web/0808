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

def main():
    """
    主函數，用於解析命令列參數並啟動模擬轉錄流程。
    """
    parser = argparse.ArgumentParser(description="一個獨立的、輕量級的模擬音訊轉錄工具。")
    parser.add_argument("audio_file", type=str, help="需要轉錄的音訊檔案路徑 (僅用於日誌記錄)。")
    parser.add_argument("output_file", type=str, help="儲存模擬轉錄結果的檔案路徑。")
    # 我們可以接受但忽略額外的參數，以保持與真實工具的介面相容
    parser.add_argument("--model_size", type=str, default="tiny", help="模型大小 (將被忽略)。")
    parser.add_argument("--language", type=str, default=None, help="音訊的語言 (將被忽略)。")

    args = parser.parse_args()

    log.info(f"🚀 (模擬) 工具啟動，參數: {args}")

    try:
        log.info("(模擬) 開始處理轉錄任務...")
        time.sleep(2) # 模擬載入模型
        log.info("(模擬) 模型載入完成，開始轉錄...")
        time.sleep(5) # 模擬轉錄過程

        result_text = f"這是一段由 mock_transcriber.py 產生的模擬轉錄結果。\n處理的檔案是：'{args.audio_file}'。"

        # 將結果寫入輸出檔案
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result_text, encoding='utf-8')

        log.info(f"✅ (模擬) 成功將結果寫入到: {args.output_file}")

    except Exception as e:
        log.critical(f"❌ (模擬) 在執行過程中發生致命錯誤: {e}", exc_info=True)
        error_file = Path(args.output_file).parent / f"{Path(args.output_file).stem}.error"
        error_file.write_text(str(e), encoding='utf-8')
        exit(1)

if __name__ == "__main__":
    main()
