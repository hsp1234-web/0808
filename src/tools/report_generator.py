import os
import logging
import subprocess
import zipfile
import gdown
import glob
import base64
import html
from weasyprint import HTML, CSS
from typing import Dict, Any

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_font() -> bool:
    """
    確保系統中存在用於產生報告的中文字體。
    """
    font_path = '/usr/share/fonts/truetype/noto/NotoSansTC-Regular.ttf'
    if os.path.exists(font_path):
        logging.info(f"✅ 中文字體已存在於: {font_path}")
        return True

    logging.info("⏳ 中文字體未找到，開始執行安裝程序...")

    font_zip_path = "/tmp/noto_sans_tc.zip"
    gdrive_id = '1NKofD5jLOI762WNvCdJNpmZQoJ5D95mG'

    logging.info(f"  [1/3] 從 Google Drive 來源下載 (ID: {gdrive_id})")
    try:
        gdown.download(id=gdrive_id, output=font_zip_path, quiet=False)
        logging.info("  ✅ 下載成功。")

        extract_path = '/tmp/noto_font_extracted'
        if os.path.exists(extract_path):
            subprocess.run(['rm', '-rf', extract_path], check=True)
        os.makedirs(extract_path)

        logging.info(f"  [2/3] 正在解壓縮字體檔案...")
        with zipfile.ZipFile(font_zip_path, 'r') as zf:
            zf.extractall(extract_path)

        logging.info(f"  [3/3] 正在搜尋並安裝字體...")
        found_font = next(iter(glob.glob(os.path.join(extract_path, '**', 'NotoSansTC-Regular.ttf'), recursive=True)), None)

        if not found_font:
            raise FileNotFoundError("在解壓縮的檔案中找不到 'NotoSansTC-Regular.ttf'")

        target_dir = os.path.dirname(font_path)
        logging.info(f"  使用 sudo 在 {target_dir} 建立目錄...")
        subprocess.run(['sudo', 'mkdir', '-p', target_dir], check=True)

        logging.info(f"  使用 sudo 將字體複製到 {font_path}...")
        subprocess.run(['sudo', 'cp', found_font, font_path], check=True)

        logging.info("  使用 sudo 更新系統字體快取...")
        subprocess.run(['sudo', 'fc-cache', '-f', '-v'], capture_output=True)

        logging.info(f"  ✅ 字體成功安裝至: {font_path}")
        return True

    except Exception as e:
        logging.error(f"  ❌ 字體安裝過程中發生錯誤: {e}")
        return False

def generate_pdf_report(extracted_data: Dict[str, Any], output_pdf_path: str) -> bool:
    """
    使用提取出的文字和圖片內容，生成一份 PDF 報告。

    :param extracted_data: 從 pdf_parser.py 得到的字典，包含 text 和 image_paths。
    :param output_pdf_path: 最終生成的 PDF 檔案路徑。
    :return: 如果成功生成則回傳 True，否則回傳 False。
    """
    logging.info(f"準備生成 PDF 報告至: {output_pdf_path}")

    # --- 1. 準備 HTML 內容 ---
    text_content = extracted_data.get("text", "")
    image_paths = extracted_data.get("image_paths", [])

    # 將純文字轉換為 HTML 段落
    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in text_content.split('\n') if p.strip())

    # 將圖片嵌入 HTML
    charts_html = ""
    if image_paths:
        charts_html = "<div class='charts-container'>"
        for img_path in image_paths:
            try:
                # 讀取圖片並進行 Base64 編碼
                with open(img_path, 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                # 取得圖片副檔名
                ext = os.path.splitext(img_path)[1].lstrip('.')
                charts_html += f"<div class='chart-item'><img src='data:image/{ext};base64,{img_b64}'><p>圖片來源: {os.path.basename(img_path)}</p></div>"
            except Exception as e:
                logging.warning(f"圖片 '{img_path}' 載入失敗: {e}")
                charts_html += f"<p>圖片 '{os.path.basename(img_path)}' 載入失敗: {e}</p>"
        charts_html += "</div>"

    # --- 2. 定義 CSS 樣式，並指定中文字體 ---
    # 這是最關鍵的一步：我們告訴 WeasyPrint 使用我們安裝的字體。
    font_css = """
    @font-face {
        font-family: 'Noto Sans TC';
        src: url('file:///usr/share/fonts/truetype/noto/NotoSansTC-Regular.ttf');
    }
    body {
        font-family: 'Noto Sans TC', sans-serif;
        line-height: 1.6;
    }
    .page-break {
        page-break-after: always;
    }
    .charts-container img {
        max-width: 80%;
        display: block;
        margin: 20px auto;
        border: 1px solid #ccc;
    }
    .chart-item {
        text-align: center;
        margin-bottom: 20px;
    }
    """

    # --- 3. 組合完整的 HTML 文件 ---
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>分析報告</title>
    </head>
    <body>
        <h1>分析報告</h1>
        <h2>文字內容</h2>
        <div class='text-content'>{paragraphs}</div>
        <hr>
        <h2>圖片內容</h2>
        {charts_html}
    </body>
    </html>
    """

    # --- 4. 使用 WeasyPrint 生成 PDF ---
    try:
        html_doc = HTML(string=html_template)
        css_doc = CSS(string=font_css)
        html_doc.write_pdf(output_pdf_path, stylesheets=[css_doc])
        logging.info(f"✅ PDF 報告成功生成於: {output_pdf_path}")
        return True
    except Exception as e:
        logging.error(f"❌ 使用 WeasyPrint 生成 PDF 時發生錯誤: {e}")
        return False
