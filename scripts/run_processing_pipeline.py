import os
import sys
import pprint
import hashlib

# 將 src 目錄添加到 Python 路徑中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.drive_downloader import download_file
from src.tools.pdf_parser import parse_pdf
from src.tools.gemini_manager import GeminiManager

def main():
    """
    執行一個使用真實 AI 的完整處理流程。
    """
    print("="*60)
    print("🚀 啟動完整處理流程 (使用真實 AI 模型)")
    print("="*60)

    # --- 0. 參數設定 ---
    # 使用者提供的 API 金鑰
    # !! 重要：在正式環境中，金鑰應透過更安全的方式 (如環境變數或加密配置) 載入
    API_KEY = "AIzaSyCkb9yr6OQ69_CK6na9RuO_ZTwg1DVxzZ8"

    # 使用者最初提供的所有 Google 相關連結
    urls_to_process = {
        "lai_jie_6799": "https://drive.google.com/file/d/1RUl7XhxyJpxKO4RBX0AxeeyD4ABYPU_l/view?usp=sharing",
        "jing_que_3162": "https://docs.google.com/document/d/16TkL54YmFAToS1UR26VdV_mYgr8bCAml/edit?tab=t.0",
        "jian_guo_5515": "https://drive.google.com/file/d/1dwnVczcEvhIIj5TOXRHVow876da6zAGp/view?usp=drivesdk",
        "long_hua_2424": "https://docs.google.com/document/d/10nDGa7nWuSZCLhU9qtR_VW8Cx-yQllk5/edit?usp=drive_link&ouid=105443695704290227678&rtpof=true&sd=true",
        "qing_wa_lang": "https://docs.google.com/document/d/1-OeWOZfZ8-KQb2-S-QhfthC7k-UPb4KofyzmLiGT17Y/edit",
        "ri_yue_guang_3711": "https://drive.google.com/file/d/1ADg9NnB10z3qjnSZPOn6BLh_Fz8wjY9T/view?usp=sharing"
    }

    download_dir = "/app/pipeline_downloads"
    image_dir = "/app/pipeline_images"

    # --- 1. 初始化 AI 管理器 ---
    print("\n[步驟 1/5] 正在初始化 AI 核心管理器...")
    try:
        # 我們將金鑰包裝成 GeminiManager 期望的格式
        api_keys_list = [{"name": "user_provided_key", "value": API_KEY}]
        ai_manager = GeminiManager(api_keys=api_keys_list)
        print("✔️ AI 管理器初始化成功。")
    except Exception as e:
        print(f"\n❌ 流程終止：AI 管理器初始化失敗: {e}")
        return

    # --- 2. 確保字體已安裝 (雖然此流程不生成報告，但保持流程完整性) ---
    # from src.tools.report_generator import setup_font
    # setup_font()

    # --- 3. 遍歷並處理所有文件 ---
    for name, url in urls_to_process.items():
        print("\n" + "="*60)
        print(f"▶️  開始處理文件: {name} ({url})")
        print("="*60)

        # 下載
        print(f"\n[步驟 2/4] 正在下載檔案...")
        file_name = f"{name}.pdf"
        downloaded_pdf_path = download_file(url, download_dir, file_name)
        if not downloaded_pdf_path:
            print(f"❌ 文件 {name} 處理失敗：下載步驟出錯。")
            continue

        # 解析
        print(f"\n[步驟 3/4] 正在解析 PDF...")
        extracted_content = parse_pdf(downloaded_pdf_path, image_dir)
        if not extracted_content:
            print(f"❌ 文件 {name} 處理失敗：解析步驟出錯。")
            continue

        # AI 分析
        print(f"\n[步驟 4/4] 正在進行真實 AI 分析...")
        # a. 分析文字
        text_analysis = ai_manager.analyze_text(extracted_content['text'])

        # b. 分析圖片
        image_analyses = []
        for img_path in extracted_content['image_paths']:
            img_analysis = ai_manager.describe_image(img_path)
            image_analyses.append({img_path: img_analysis})

        # --- 4. 輸出結果 ---
        print("\n" + "-"*25 + " 分析結果 " + "-"*25)
        print("\n>>> 文字分析結果:")
        pprint.pprint(text_analysis)

        print("\n>>> 圖片分析結果:")
        pprint.pprint(image_analyses)
        print("-" * 60)

    print("\n🎉 所有文件處理完畢。")

if __name__ == "__main__":
    main()
