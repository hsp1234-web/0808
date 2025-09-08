# -*- coding: utf-8 -*-
import google.generativeai as genai
import os
import argparse

def list_available_models(api_key: str):
    """
    使用指定的 API 金鑰，列出所有可用的、支援 'generateContent' 方法的 Gemini 模型。
    """
    if not api_key:
        print("錯誤：未提供 API 金鑰。請使用 --api-key 參數或設定 GOOGLE_API_KEY 環境變數。")
        return

    try:
        genai.configure(api_key=api_key)
        print("成功設定 API 金鑰。正在查詢模型列表...")

        print("\n--- 可用的 Gemini 模型 (支援 'generateContent') ---")
        for m in genai.list_models():
            # 我們只關心能生成文字內容的模型
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
        print("--------------------------------------------------")
        print("\n查詢完成。請從以上列表中選擇一個模型名稱。")

    except Exception as e:
        print(f"查詢模型時發生錯誤: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查詢可用的 Google Gemini 模型。")
    parser.add_argument("--api-key", type=str, dest="api_key",
                        help="Google API 金鑰。如果未提供，將嘗試從 GOOGLE_API_KEY 環境變數讀取。")

    args = parser.parse_args()

    # 獲取 API 金鑰
    key = args.api_key or os.environ.get("GOOGLE_API_KEY")

    list_available_models(key)
