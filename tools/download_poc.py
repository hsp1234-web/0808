# -*- coding: utf-8 -*-
import sys
import argparse
import logging

# 設定一個簡單的日誌記錄器，以便觀察 huggingface_hub 的行為
logging.basicConfig(level=logging.INFO)
logging.getLogger("huggingface_hub").setLevel(logging.INFO)

def download_model(model_name: str, download_path: str):
    """
    下載或驗證一個 faster-whisper 模型到指定路徑。

    這個函數會觸發 faster_whisper.WhisperModel 的初始化。
    如果模型尚未被下載到 `download_path`，底層的 `huggingface_hub`
    將會自動從網路上下載，並將進度條顯示在 stderr。

    Args:
        model_name (str): 欲下載的模型名稱，例如 'medium'。
        download_path (str): 儲存模型的目標根目錄。
    """
    print(f"指令碼：準備下載或驗證模型 '{model_name}'...")
    print(f"指令碼：模型將儲存於 '{download_path}' 目錄下。")

    # 為了能捕捉進度條，我們需要延後匯入 WhisperModel
    # 確保 logging 設定在匯入前生效
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("錯誤：缺少 'faster-whisper' 套件。請先安裝。", file=sys.stderr)
        sys.exit(1)

    try:
        # 這個操作會自動從 Hugging Face Hub 下載模型（如果本地快取不存在）
        # 下載進度條會由 huggingface_hub library 直接輸出到 stderr
        # 我們不需要儲存這個 model 物件，目的只是觸發下載。
        _ = WhisperModel(
            model_size_or_path=model_name,
            download_root=download_path
        )
        print(f"指令碼：模型 '{model_name}' 已成功下載或驗證。")
    except Exception as e:
        print(f"指令碼：下載模型時發生嚴重錯誤: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="下載指定的 faster-whisper 模型。此腳本設計為由其他腳本呼叫。"
    )
    parser.add_argument(
        "--model_name",
        type=str,
        required=True,
        help="要下載的模型名稱 (例如 'medium')。"
    )
    parser.add_argument(
        "--download_path",
        type=str,
        required=True,
        help="儲存模型的根目錄路徑。"
    )
    args = parser.parse_args()

    download_model(args.model_name, args.download_path)
