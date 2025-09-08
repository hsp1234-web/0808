import fitz  # PyMuPDF
import os
import logging
from typing import Dict, List, Any

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_pdf(pdf_path: str, image_output_dir: str) -> Dict[str, Any]:
    """
    解析一個 PDF 檔案，提取其所有文字和圖片。

    :param pdf_path: 要處理的 PDF 檔案路徑。
    :param image_output_dir: 用於儲存提取出的圖片的目錄。
    :return: 一個包含提取內容的字典，格式為：
             {
                 "text": "完整的文字內容",
                 "image_paths": ["圖片1的路徑", "圖片2的路徑", ...],
                 "page_count": 頁數
             }
             如果失敗則回傳 None。
    """
    if not os.path.exists(pdf_path):
        logging.error(f"找不到指定的 PDF 檔案：{pdf_path}")
        return None

    os.makedirs(image_output_dir, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logging.error(f"使用 PyMuPDF 開啟檔案 '{pdf_path}' 失敗: {e}")
        return None

    all_text = []
    extracted_image_paths = []

    try:
        # 遍歷每一頁
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)

            # 1. 提取文字
            all_text.append(page.get_text())

            # 2. 提取圖片
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # 儲存圖片
                pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
                image_filename = f"{pdf_filename}_page{page_num+1}_img{img_index}.{image_ext}"
                image_path = os.path.join(image_output_dir, image_filename)

                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)
                extracted_image_paths.append(image_path)

        logging.info(f"✅ 成功解析 '{pdf_path}'. 找到 {doc.page_count} 頁, {len(extracted_image_paths)} 張圖片。")

        return {
            "text": "\n".join(all_text),
            "image_paths": extracted_image_paths,
            "page_count": doc.page_count
        }

    except Exception as e:
        logging.error(f"處理 PDF '{pdf_path}' 過程中發生錯誤: {e}")
        return None
    finally:
        doc.close()

if __name__ == '__main__':
    # 這是一個當此檔案被直接執行時的測試區塊
    print("正在執行 pdf_parser.py 的單元測試...")

    # 假設我們已經下載了這個檔案
    test_pdf_path = "/app/downloads/lai_jie_6799_file.pdf"
    test_image_output = "/app/temp_test_images"

    if os.path.exists(test_pdf_path):
        print(f"\n--- 測試解析檔案: {test_pdf_path} ---")
        extracted_data = parse_pdf(test_pdf_path, test_image_output)

        if extracted_data:
            print(f"✔️ 測試成功！")
            print(f"   - 頁數: {extracted_data['page_count']}")
            print(f"   - 圖片數量: {len(extracted_data['image_paths'])}")
            print(f"   - 文字預覽: {extracted_data['text'][:200]}...")
            print(f"   - 圖片儲存於: {test_image_output}")
        else:
            print(f"❌ 測試失敗")
    else:
        print(f"⚠️ 跳過測試，因為找不到測試檔案: {test_pdf_path}")

    print("\n單元測試完畢。")
