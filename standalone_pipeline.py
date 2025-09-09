# ==============================================================================
# 整合式獨立執行腳本
# 建立者：Jules
# 日期：2025-09-08
#
# 說明：
# 此腳本將專案中多個模組的功能合併至單一檔案中，以便於移植和獨立執行。
# 它包含了從 Google Drive 下載文件、解析 PDF、使用 Gemini AI 分析內容，
# 到最終生成圖文並茂的 PDF 報告的完整流程。
#
# 如何執行：
# 1. 將您的 Google Gemini API 金鑰填入下方的 `API_KEY` 變數中。
# 2. 執行指令：`python standalone_pipeline.py`
# 3. 最終報告將會生成在 `/app/standalone_report.pdf`。
#
# 注意：此腳本需要在一個已安裝好所有依賴套件的環境中執行。
# 必要套件：gdown, PyMuPDF, weasyprint, google-generativeai, pillow
# ==============================================================================

import os
import sys
import logging
import subprocess
import zipfile
import gdown
import glob
import base64
import html
import json
import time
import threading
import pprint
from collections import deque
from typing import List, Optional, Tuple, Dict, Any

# --- 1. 全域設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# JULES: Because this is a standalone script, we need to handle potential imports
# that might not be available. We'll create dummy classes/functions if they are missing.
try:
    import fitz # PyMuPDF
except ImportError:
    logging.warning("PyMuPDF (fitz) not found. PDF parsing will be disabled.")
    fitz = None

try:
    from weasyprint import HTML, CSS
except ImportError:
    logging.warning("WeasyPrint not found. PDF report generation will be disabled.")
    HTML, CSS = None, None

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    from PIL import Image
except ImportError:
    logging.warning("google-generativeai or pillow not found. AI analysis will be disabled.")
    genai = None
    Image = None
    GenerationConfig = None


# ==============================================================================
# 區塊 2：核心功能函式與類別 (從 src/tools/ 模組整合而來)
# ==============================================================================

# --- From: drive_downloader.py ---
def download_file(url: str, output_dir: str, file_name: str = None) -> str:
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, file_name) if file_name else output_dir
    logging.info(f"準備從 URL 下載：{url}")
    try:
        downloaded_path = gdown.download(url, output_path, quiet=False, fuzzy=True)
        if downloaded_path and os.path.exists(downloaded_path):
            logging.info(f"✅ 檔案成功下載至：{downloaded_path}")
            return downloaded_path
        else:
            logging.error("❌ 下載失敗：gdown 執行完畢但未回傳有效的檔案路徑。")
            return None
    except Exception as e:
        logging.error(f"❌ 下載過程中發生嚴重錯誤：{e}")
        return None

# --- From: pdf_parser.py ---
def parse_pdf(pdf_path: str, image_output_dir: str) -> Dict[str, Any]:
    if not fitz:
        logging.error("無法解析 PDF，因為 PyMuPDF (fitz) 模組未安裝。")
        return None
    if not os.path.exists(pdf_path):
        logging.error(f"找不到指定的 PDF 檔案：{pdf_path}")
        return None
    os.makedirs(image_output_dir, exist_ok=True)
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logging.error(f"使用 PyMuPDF 開啟檔案 '{pdf_path}' 失敗: {e}")
        return None
    all_text, extracted_image_paths = [], []
    try:
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            all_text.append(page.get_text())
            for img_index, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes, image_ext = base_image["image"], base_image["ext"]
                pdf_filename = os.path.splitext(os.path.basename(pdf_path))[0]
                image_filename = f"{pdf_filename}_page{page_num+1}_img{img_index}.{image_ext}"
                image_path = os.path.join(image_output_dir, image_filename)
                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)
                extracted_image_paths.append(image_path)
        logging.info(f"✅ 成功解析 '{pdf_path}'. 找到 {doc.page_count} 頁, {len(extracted_image_paths)} 張圖片。")
        return {"text": "\n".join(all_text), "image_paths": extracted_image_paths, "page_count": doc.page_count}
    except Exception as e:
        logging.error(f"處理 PDF '{pdf_path}' 過程中發生錯誤: {e}")
        return None
    finally:
        doc.close()

# --- From: report_generator.py ---
def setup_font() -> bool:
    font_path = '/usr/share/fonts/truetype/noto/NotoSansTC-Regular.ttf'
    if os.path.exists(font_path):
        logging.info(f"✅ 中文字體已存在於: {font_path}")
        return True
    logging.info("⏳ 中文字體未找到，開始執行安裝程序...")
    font_zip_path, gdrive_id = "/tmp/noto_sans_tc.zip", '1NKofD5jLOI762WNvCdJNpmZQoJ5D95mG'
    try:
        gdown.download(id=gdrive_id, output=font_zip_path, quiet=False)
        extract_path = '/tmp/noto_font_extracted'
        if os.path.exists(extract_path): subprocess.run(['rm', '-rf', extract_path], check=True)
        os.makedirs(extract_path)
        with zipfile.ZipFile(font_zip_path, 'r') as zf: zf.extractall(extract_path)
        found_font = next(iter(glob.glob(os.path.join(extract_path, '**', 'NotoSansTC-Regular.ttf'), recursive=True)), None)
        if not found_font: raise FileNotFoundError("在解壓縮的檔案中找不到 'NotoSansTC-Regular.ttf'")
        target_dir = os.path.dirname(font_path)
        subprocess.run(['sudo', 'mkdir', '-p', target_dir], check=True)
        subprocess.run(['sudo', 'cp', found_font, font_path], check=True)
        subprocess.run(['sudo', 'fc-cache', '-f', '-v'], capture_output=True)
        logging.info(f"✅ 字體成功安裝至: {font_path}")
        return True
    except Exception as e:
        logging.error(f"❌ 字體安裝過程中發生錯誤: {e}")
        return False

def generate_final_report(report_data: Dict[str, Any], output_pdf_path: str) -> bool:
    if not HTML or not CSS:
        logging.error("無法生成 PDF 報告，因為 WeasyPrint 模組未安裝。")
        return False
    logging.info(f"準備生成 PDF 報告至: {output_pdf_path}")
    text_content = report_data.get("original_content", {}).get("text", "")
    image_paths = report_data.get("original_content", {}).get("image_paths", [])
    text_analysis = report_data.get("ai_analysis", {}).get("text_analysis", {})
    image_analyses = report_data.get("ai_analysis", {}).get("image_analyses", [])

    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in text_content.split('\n') if p.strip())

    summary_html = f"<h3>AI 文字摘要</h3><p>{html.escape(text_analysis.get('summary', '無'))}</p>"
    keywords_html = f"<h3>AI 關鍵字</h3><p>{', '.join(text_analysis.get('keywords', []))}</p>"

    charts_html = ""
    img_analysis_map = {list(item.keys())[0]: list(item.values())[0] for item in image_analyses}
    for img_path in image_paths:
        try:
            with open(img_path, 'rb') as f: img_b64 = base64.b64encode(f.read()).decode()
            ext = os.path.splitext(img_path)[1].lstrip('.')
            desc = img_analysis_map.get(img_path, {}).get('description', '無可用描述')
            charts_html += f"<div class='chart-item'><img src='data:image/{ext};base64,{img_b64}'><p><b>AI 描述:</b> {html.escape(desc)}</p></div>"
        except Exception as e:
            charts_html += f"<p>圖片 '{os.path.basename(img_path)}' 載入失敗: {e}</p>"

    font_css = """@font-face {font-family: 'Noto Sans TC'; src: url('file:///usr/share/fonts/truetype/noto/NotoSansTC-Regular.ttf');} body {font-family: 'Noto Sans TC', sans-serif; line-height: 1.6;} .chart-item img {max-width: 80%; display: block; margin: 20px auto; border: 1px solid #ccc;} .chart-item p {text-align: center; margin-top: 5px;}"""
    html_template = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>分析報告</title></head><body><h1>分析報告</h1><h2>AI 分析結果</h2>{summary_html}{keywords_html}<hr><h2>原始文字內容</h2>{paragraphs}<hr><h2>圖片內容</h2>{charts_html}</body></html>"""

    try:
        HTML(string=html_template).write_pdf(output_pdf_path, stylesheets=[CSS(string=font_css)])
        logging.info(f"✅ PDF 報告成功生成於: {output_pdf_path}")
        return True
    except Exception as e:
        logging.error(f"❌ 使用 WeasyPrint 生成 PDF 時發生錯誤: {e}")
        return False

# --- From: gemini_manager.py ---
class ApiKey:
    def __init__(self, key_value: str, name: str): self.key, self.name = key_value, name
class GeminiManager:
    def __init__(self, api_keys: List[Dict[str, str]], timeout: int = 180, max_retries: int = 3):
        if not genai:
            raise ImportError("GeminiManager 無法初始化，因為 google.generativeai 模組未安裝。")
        if not api_keys: raise ValueError("API 金鑰列表不可為空。")
        self.key_pool = deque([ApiKey(key_value=k['value'], name=k['name']) for k in api_keys])
        self.timeout, self.max_retries, self._lock = timeout, max_retries, threading.Lock()
        logging.info(f"Gemini 管理器已初始化，共載入 {len(self.key_pool)} 組 API 金鑰。")
    def _get_key(self) -> ApiKey:
        with self._lock: key = self.key_pool[0]; self.key_pool.rotate(-1); return key
    def _api_call_wrapper(self, task_name: str, model_name: str, prompt_content: List[Any]):
        if not genai: return None, "google.generativeai not installed", "N/A"
        api_key, last_error = self._get_key(), None
        for attempt in range(self.max_retries):
            tag = f"{task_name}-{api_key.name}"
            logging.info(f"[{tag}] 正在執行 API 請求 (使用模型: {model_name}, 第 {attempt + 1}/{self.max_retries} 次嘗試)...")
            try:
                genai.configure(api_key=api_key.key)
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt_content, generation_config=GenerationConfig(response_mime_type="application/json"), request_options={'timeout': self.timeout})
                raw_text = response.text
                if not raw_text: raise ValueError("API 回傳空內容")
                if raw_text.strip().startswith("```json"): raw_text = raw_text.strip()[7:-3].strip()
                return json.loads(raw_text), None, api_key.name
            except Exception as e:
                last_error, last_error_str = e, f"{type(e).__name__}: {e}"
                if any(s in last_error_str.lower() for s in ["500", "503", "timed out", "deadline", "aborted", "reset", "quota"]) and attempt < self.max_retries - 1:
                    logging.warning(f"[{tag}] 請求失敗 (可重試)，{2**(attempt+1)} 秒後重試..."); time.sleep(2**(attempt+1)); continue
                break
        logging.error(f"[{tag}] 經過 {self.max_retries} 次嘗試後，API 請求最終失敗: {last_error}")
        return None, last_error, api_key.name
    def analyze_text(self, text_content: str, model_name: str = "gemini-1.5-flash-latest") -> Optional[Dict]:
        prompt = f"你是一位專業的內容分析師。請閱讀以下文章，並以 JSON 格式回傳包含以下兩個鍵的物件：1. `summary` (string): 對文章內容的簡短摘要。2. `keywords` (list of strings): 從文章中提取的 3-5 個核心關鍵字。\n\n文章內容如下：\n---\n{text_content}\n---\n請直接回傳 JSON 物件，不要包含任何額外的解釋或 Markdown 標記。"
        result, _, _ = self._api_call_wrapper(task_name="AnalyzeText", model_name=model_name, prompt_content=[prompt]); return result
    def describe_image(self, image_path: str, model_name: str = "gemini-1.5-flash-latest") -> Optional[Dict]:
        if not Image: return None
        try: img = Image.open(image_path)
        except Exception as e: logging.error(f"無法開啟圖片檔案 '{image_path}': {e}"); return None
        prompt = "你是一位圖像分析專家。請描述這張圖片的內容。如果它是一張圖表，請說明它的類型以及它可能在傳達的資訊。\n請以 JSON 格式回傳包含以下兩個鍵的物件：1. `description` (string): 對圖片內容的詳細描述。2. `chart_type` (string): 如果是圖表，請指出其類型（例如 '長條圖', '折線圖', '圓餅圖'）。如果不是圖表，則回傳 '非圖表'。"
        result, _, _ = self._api_call_wrapper(task_name="DescribeImage", model_name=model_name, prompt_content=[prompt, img]); return result

# ==============================================================================
# 區塊 3：主執行流程 (從 scripts/run_processing_pipeline.py 整合而來)
# ==============================================================================
def main_pipeline():
    print("="*60 + "\n🚀 啟動整合式獨立處理流程\n" + "="*60)
    # --- 參數設定 ---
    API_KEY = os.environ.get("GOOGLE_API_KEY", "YOUR_API_KEY_HERE") # 從環境變數讀取或使用預設值
    if API_KEY == "YOUR_API_KEY_HERE":
        logging.warning("警告：未設定 GOOGLE_API_KEY 環境變數，請在執行前設定。")

    urls_to_process = {
        "lai_jie_6799": "https://drive.google.com/file/d/1RUl7XhxyJpxKO4RBX0AxeeyD4ABYPU_l/view?usp=sharing",
        "jing_que_3162": "https://docs.google.com/document/d/16TkL54YmFAToS1UR26VdV_mYgr8bCAml/edit?tab=t.0",
    }
    download_dir, image_dir = "/app/standalone_downloads", "/app/standalone_images"
    report_output_path = "/app/standalone_report.pdf"

    # --- 流程開始 ---
    print("\n[步驟 1/5] 正在檢查並設定中文字體...")
    if not setup_font(): print("\n❌ 流程終止：中文字體安裝失敗。"); return

    print("\n[步驟 2/5] 正在初始化 AI 核心管理器...")
    try:
        ai_manager = GeminiManager(api_keys=[{"name": "user_provided_key", "value": API_KEY}])
        print("✔️ AI 管理器初始化成功。")
    except Exception as e: print(f"\n❌ 流程終止：AI 管理器初始化失敗: {e}"); return

    all_results = []
    print("\n[步驟 3/5] 開始逐一處理文件...")
    for name, url in urls_to_process.items():
        print("\n" + "="*60 + f"\n▶️  開始處理文件: {name}\n" + "="*60)
        downloaded_pdf_path = download_file(url, download_dir, f"{name}.pdf")
        if not downloaded_pdf_path: continue

        extracted_content = parse_pdf(downloaded_pdf_path, image_dir)
        if not extracted_content: continue

        print("\n[步驟 4/5] 正在進行 AI 分析...")
        text_analysis = ai_manager.analyze_text(extracted_content['text'])
        image_analyses = [ {img_path: ai_manager.describe_image(img_path)} for img_path in extracted_content['image_paths'] ]

        final_data = {
            "source_doc": name,
            "original_content": extracted_content,
            "ai_analysis": {"text_analysis": text_analysis, "image_analyses": image_analyses}
        }
        all_results.append(final_data)
        print("\n--- 分析結果預覽 ---")
        pprint.pprint(final_data)
        print("--- 預覽結束 ---")


    print("\n[步驟 5/5] 正在生成最終的 PDF 分析報告...")
    # 為了示範，我們只用第一份文件的結果來生成報告
    if all_results:
        generate_final_report(all_results[0], report_output_path)
    else:
        print("沒有任何文件成功處理，無法生成報告。")

    print("\n🎉 所有文件處理完畢！")

if __name__ == "__main__":
    main_pipeline()
