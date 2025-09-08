import os
import sys
import pprint

# 將 src 目錄添加到 Python 路徑中，這樣我們就可以匯入我們的模組
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.drive_downloader import download_file
from src.tools.pdf_parser import parse_pdf

def main():
    """
    執行一個完整的處理流程：從 URL 下載 -> 解析 PDF -> 提取內容
    """
    print("="*60)
    print("🚀 啟動完整處理流程測試腳本 (總指揮官原型)")
    print("="*60)

    # --- 參數設定 ---
    # 我們將使用一個包含文字和圖片的複雜 PDF 作為測試目標
    test_url = "https://drive.google.com/file/d/1RUl7XhxyJpxKO4RBX0AxeeyD4ABYPU_l/view?usp=sharing"
    download_dir = "/app/pipeline_downloads"
    image_dir = "/app/pipeline_images"

    # --- 步驟 1: 下載檔案 ---
    print(f"\n[步驟 1/2] 正在從 URL 下載檔案...")
    print(f"URL: {test_url}")

    downloaded_pdf_path = download_file(test_url, download_dir, "test_document.pdf")

    if not downloaded_pdf_path:
        print("\n❌ 流程終止：檔案下載失敗。")
        return

    print(f"✔️ 檔案下載成功，儲存於: {downloaded_pdf_path}")

    # --- 步驟 2: 解析 PDF 並提取內容 ---
    print(f"\n[步驟 2/2] 正在解析 PDF 檔案並提取內容...")

    extracted_content = parse_pdf(downloaded_pdf_path, image_dir)

    if not extracted_content:
        print("\n❌ 流程終止：PDF 內容提取失敗。")
        return

    print("\n" + "="*60)
    print("🎉 流程成功完成！以下是提取出的內容摘要：")
    print("="*60)

    # 使用 pprint 美化輸出
    pprint.pprint(extracted_content)


if __name__ == "__main__":
    main()
