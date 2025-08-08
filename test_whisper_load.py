# -*- coding: utf-8 -*-
# 檔案: tools/test_whisper_load.py
# 說明: 一個極簡的腳本，專門用於測試 faster_whisper 模型載入是否會導致崩潰。

import sys
import traceback

def test_load():
    print("--- 開始測試 Whisper 模型載入 ---")
    try:
        print("步驟 1: 正在導入 WhisperModel...")
        from faster_whisper import WhisperModel
        print("導入成功！")

        print("步驟 2: 正在實例化模型 (size: tiny, device: cpu)...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("模型實例化成功！")

        print("\n✅✅✅ 測試成功！faster_whisper 可以在此環境中被正常載入。")

    except Exception as e:
        print("\n❌❌❌ 測試失敗！載入過程中發生錯誤。", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    test_load()
