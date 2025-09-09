# scripts/verify_gemini_key.py
import argparse
import sys
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

def verify_key(api_key: str):
    """
    使用給定的 API 金鑰，嘗試獲取並列出可用的 Gemini 模型。
    """
    print(f"🔑 正在使用提供的 API 金鑰進行驗證...")

    if not api_key:
        print("❌ 錯誤：未提供 API 金鑰。")
        sys.exit(1)

    try:
        # 設定 API 金鑰
        genai.configure(api_key=api_key)

        # 嘗試列出模型
        print("⏳ 正在向 Google API 發送請求以獲取模型列表...")
        models = genai.list_models()

        print("\n" + "="*30)
        print("✅ 金鑰驗證成功！可用的模型列表：")
        print("="*30)

        found_models = False
        for m in models:
            # 我們只關心支援 'generateContent' 的模型
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.display_name} (ID: {m.name})")
                found_models = True

        if not found_models:
            print("🤔 雖然金鑰有效，但未找到任何支援 'generateContent' 的模型。")

        print("\n" + "="*30)
        print("🎉 PoC 驗證成功完成。")

    except google_exceptions.PermissionDenied as e:
        print("\n" + "="*30)
        print("❌ 驗證失敗：權限被拒絕。")
        print("="*30)
        print("這通常表示您的 API 金鑰無效、已過期，或未在您的 Google Cloud 專案中啟用 Generative Language API。")
        print(f"詳細錯誤訊息: {e}")
        sys.exit(1)

    except Exception as e:
        print("\n" + "="*30)
        print(f"❌ 發生未預期的錯誤：{type(e).__name__}")
        print("="*30)
        print("請檢查您的網路連線，或查看以下的詳細錯誤訊息。")
        print(f"詳細錯誤訊息: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一個用於驗證 Google Gemini API 金鑰的 PoC 腳本。")
    parser.add_argument(
        "--key",
        type=str,
        required=True,
        help="要進行驗證的 Google API 金鑰。"
    )
    args = parser.parse_args()

    verify_key(args.key)
