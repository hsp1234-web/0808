# -*- coding: utf-8 -*-
# tools/gemini_processor.py
import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

# --- 日誌設定 ---
# 設定日誌記錄器，確保所有輸出都進入 stdout，以便父程序擷取
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # 強制使用 sys.stdout，避免日誌記錄到 stderr
    stream=sys.stdout
)
log = logging.getLogger('gemini_processor_tool')

# --- 輔助函式 (來自 damo.py) ---
def sanitize_filename(title: str, max_len: int = 60) -> str:
    """清理檔案名稱，移除無效字元並取代空格。"""
    if not title:
        title = "untitled_document"
    # 移除非法字元
    title = re.sub(r'[\\/*?:"<>|]', "_", title)
    title = title.replace(" ", "_")
    # 將多個底線縮減為一個
    title = re.sub(r"_+", "_", title)
    # 去除開頭和結尾的底線
    title = title.strip('_')
    return title[:max_len]

def print_progress(status: str, detail: str, extra_data: dict = None):
    """以標準 JSON 格式輸出進度到 stdout。"""
    progress_data = {
        "type": "progress",
        "status": status,
        "detail": detail
    }
    if extra_data:
        progress_data.update(extra_data)
    print(json.dumps(progress_data), flush=True)

# --- 提示詞 (Prompts from damo.py) ---
SUMMARY_TRANSCRIPT_PROMPT = """請您扮演一位專業的逐字稿分析師。
您將收到一個名為 '{original_filename}' (原始影片標題為: '{video_title}') 的音訊檔案。請完成以下兩項任務，並嚴格依照指定格式（包含標記）輸出，所有文字內容請使用繁體中文（台灣用語習慣）：

任務一：重點摘要
請根據音訊內容，簡潔扼要地總結其核心內容與主要觀點。摘要應包含一個總體主旨的開頭段落，以及數個帶有粗體子標題的重點條目，每個條目下使用無序列表列出關鍵細節。請勿包含時間戳記。

任務二：詳細逐字稿
請提供完整的逐字稿。如果內容包含多位發言者，請嘗試區分（例如：發言者A, 發言者B）。對於專有名詞、品牌名稱、人名等，請盡可能以「中文 (English)」的格式呈現。

輸出格式範例（請嚴格遵守此分隔方式與標記）：
[重點摘要開始]
[此處為您的重點摘要內容，包含總體主旨和帶子標題的條目，使用繁體中文]
[重點摘要結束]

---[逐字稿分隔線]---

[詳細逐字稿開始]
[此處為您的詳細逐字稿內容，使用繁體中文]
[詳細逐字稿結束]
"""

HTML_GENERATION_PROMPT = """請生成一個完整的HTML檔案，該檔案應包含響應式設計（Responsive Web Design）的考量，並將提供的內容整合成一個頁面。所有文字內容請使用繁體中文（台灣用語習慣）。頁面內容分為兩大部分：「重點摘要」和「逐字稿」。

**自動生成的「影片標題」應作為頁面的主要H1標題。**

**自動生成的「重點摘要」部分必須包含以下元素和要求（使用繁體中文）：**
* 一個開頭的段落，簡要說明音訊的整體主旨。
* 多個重點條目，每個條目都應該有一個**粗體**的子標題（例如：「**1. 專注力的普遍適用性**」）。
* 在每個重點條目下，使用無序列表 (`<ul>` 和 `<li>`) 形式，簡潔地列出該重點下的關鍵細節。
* 重點條目和其下的細節應精煉、準確地反映逐字稿中的核心思想和關鍵資訊。
* 請勿在「重點摘要」部分包含時間戳記。

**生成的HTML檔案，除了上述內容生成要求外，需全面滿足以下排版、功能和響應式設計要求：**

1.  **響應式設計 (Responsive Design)：**
    * 頁面應能良好適應不同尺寸的螢幕（從5.5吋手機到22吋電腦螢幕），提供最佳閱讀體驗。
    * 在 `<head>` 中包含 `<meta name="viewport" content="width=device-width, initial-scale=1.0">`。
    * 圖片 (`<img>`) 應具備彈性，設定 `max-width: 100%; height: auto; display: block;` (如果內容中包含圖片)。
    * 利用媒體查詢 (Media Queries) 針對不同螢幕斷點（例如：手機為 `max-width: 480px`，平板為 `min-width: 481px` and `max-width: 768px`，桌面為 `min-width: 769px`）調整 CSS 樣式，包括：
        * `font-size` (字體大小) - 應使用 `rem` 單位。
        * `line-height` (行高)。
        * `margin` 和 `padding` (邊距與內邊距)。
        * `hr` (水平線) 的樣式。
    * 內容主體應限制最大寬度（例如 `max-width: 900px;`）並置中 (`margin: 0 auto;`)，避免在大螢幕下閱讀行長度過長。
    * 採用行動優先 (Mobile-First) 設計原則，基礎樣式適用於小螢幕，再逐步擴展。

2.  **排版與易讀性 (Layout & Readability)：**
    * **無縮排：** 段落 (`<p>`) 和列表項目 (`<li>`) 應完全靠左對齊，無首行縮排 (`text-indent: 0;`)。
    * **水平線整理：** 大量使用 `<hr>` 標籤作為視覺分隔，並透過 CSS 美化，使其具有清晰的區隔感（例如：`border: 0; height: 1.5px;`），並有足夠的上下邊距。
    * **層次清晰：** 使用 `<h1>`, `<h2>`, `<h3>` 等標題標籤來表示內容層次，並透過 CSS 調整其字體大小和顏色，使其易於識別。
        * `<h1>` 應居中並有底部邊框。
        * `<h2>` 應靠左對齊，有底部邊框和強調色。
        * `<h3>` 應靠左對齊，字體大小適中。
    * **字體與間距：** 選擇易讀的字體 (例如：'微軟正黑體', 'Arial', sans-serif)，設定適中的行高（例如 `line-height: 1.7;`）和段落間距，提升閱讀舒適度。
    * **強調文字：** 重要概念和關鍵詞使用 `<strong>` 標籤加粗，並設定醒目顏色。
    * 列表項目 (`<ul>`) 應有適當的左邊距，嵌套列表 (`<ul><ul>`) 應有不同的列表樣式（例如 `circle`）。

3.  **暗色模式 (Dark Mode) 功能：**
    * 實作一個可切換的暗色模式功能。
    * 使用 CSS 變數 (`:root` 和 `body.dark-mode`) 來定義淺色和暗色模式下的**所有**顏色方案，包括背景色、內文文字顏色、標題顏色、強調色/連結色、加粗文字顏色、水平線顏色，以及**按鈕的背景色和文字顏色**，以確保足夠的對比度，提升暗色模式下的閱讀體驗。請確保不同元素在兩種模式下的顏色值都能提供良好的對比度。
    * 在頁面右上角固定一個功能按鈕容器 (`.controls-container`)，包含一個切換按鈕 (`<button id="darkModeToggle" class="control-button">`)，允許使用者手動切換模式。
    * 使用 JavaScript 處理按鈕點擊事件，切換 `<body>` 元素的 `dark-mode` 類別。
    * JavaScript 應能偵測使用者系統的暗色模式偏好，並將用戶的模式選擇儲存到 `localStorage` 中，以便下次訪問時保持相同的模式。
    * 顏色切換應具有平滑的過渡效果 (`transition`)。

4.  **字體大小調整功能：**
    * 實作三個按鈕 (`<button id="fontSmall" class="control-button">`, `<button id="fontMedium" class="control-button">`, `<button id="fontLarge" class="control-button">`)，分別對應「小」、「中」、「大」三種字體大小，並放置在上述功能按鈕容器中。
    * 使用 CSS 變數 (`--base-font-size`) 來控制 HTML 根元素 (`<html>`) 的基礎字體大小，所有其他字體大小應使用 `rem` 單位，以實現統一縮放。
    * JavaScript 應處理按鈕點擊事件，動態更新 `--base-font-size` 變數。
    * 用戶的字體大小選擇應儲存到 `localStorage` 中，以便下次訪問時保持相同的偏好。
    * 字體大小切換應具有平滑的過渡效果 (`transition`)。

**以下是需要嵌入的內容（請確保這些內容也使用繁體中文）：**

影片標題：
---[影片標題開始]---
{video_title_for_html}
---[影片標題結束]---

重點摘要內容：
---[重點摘要內容開始]---
{summary_text_for_html}
---[重點摘要內容結束]---

逐字稿內容：
---[逐字稿內容開始]---
{transcript_text_for_html}
---[逐字稿內容結束]---

請嚴格按照上述要求，將提供的「影片標題」、「重點摘要內容」和「逐字稿內容」填充到生成的HTML的相應位置。確保最終輸出的是一個可以直接使用的、包含所有 CSS 和 JavaScript 的完整 HTML 檔案內容，以 `<!DOCTYPE html>` 開頭。
"""

# --- 核心 Gemini 處理函式 ---

def upload_to_gemini(genai_module, audio_path: Path, display_filename: str):
    """上傳檔案至 Gemini Files API。"""
    log.info(f"☁️ Uploading '{display_filename}' to Gemini Files API...")
    print_progress("uploading", f"正在上傳音訊檔案 {display_filename}...")
    try:
        # 偵測 MIME 類型
        ext = audio_path.suffix.lower()
        mime_map = {'.mp3': 'audio/mp3', '.m4a': 'audio/m4a', '.aac': 'audio/aac',
                    '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.flac': 'audio/flac',
                    '.webm': 'audio/webm', '.mp4': 'audio/mp4'}
        mime_type = mime_map.get(ext, 'application/octet-stream')
        if mime_type in ['audio/m4a', 'audio/mp4']:
            mime_type = 'audio/aac' # Gemini 偏好 aac

        audio_file_resource = genai_module.upload_file(
            path=str(audio_path),
            display_name=display_filename,
            mime_type=mime_type
        )
        log.info(f"✅ Upload successful. Gemini File URI: {audio_file_resource.uri}")
        print_progress("upload_complete", "音訊上傳成功。")
        return audio_file_resource
    except Exception as e:
        log.critical(f"🔴 Failed to upload file to Gemini: {e}", exc_info=True)
        raise

def get_summary_and_transcript(genai_module, gemini_file_resource, model_api_name: str, video_title: str, original_filename: str):
    """使用 Gemini 模型生成摘要與逐字稿。"""
    log.info(f"🤖 Requesting summary and transcript from model '{model_api_name}'...")
    print_progress("generating_transcript", "AI 正在生成摘要與逐字稿...")
    prompt = SUMMARY_TRANSCRIPT_PROMPT.format(original_filename=original_filename, video_title=video_title)
    try:
        model = genai_module.GenerativeModel(model_api_name)
        response = model.generate_content([prompt, gemini_file_resource], request_options={'timeout': 3600})
        full_response_text = response.text

        summary_match = re.search(r"\[重點摘要開始\](.*?)\[重點摘要結束\]", full_response_text, re.DOTALL)
        summary_text = summary_match.group(1).strip() if summary_match else "未擷取到重點摘要。"

        transcript_match = re.search(r"\[詳細逐字稿開始\](.*?)\[詳細逐字稿結束\]", full_response_text, re.DOTALL)
        transcript_text = transcript_match.group(1).strip() if transcript_match else "未擷取到詳細逐字稿。"

        if "未擷取到" in summary_text and "未擷取到" in transcript_text and "---[逐字稿分隔線]---" not in full_response_text:
            transcript_text = full_response_text
            summary_text = "（自動摘要失敗，請參考下方逐字稿自行整理）"

        log.info("✅ Successfully generated summary and transcript.")
        print_progress("transcript_generated", "摘要與逐字稿生成完畢。")
        return summary_text, transcript_text
    except Exception as e:
        log.critical(f"🔴 Failed to get summary/transcript from Gemini: {e}", exc_info=True)
        raise

def generate_html_report(genai_module, summary_text: str, transcript_text: str, model_api_name: str, video_title: str):
    """使用 Gemini 模型生成 HTML 報告。"""
    log.info(f"🎨 Requesting HTML report from model '{model_api_name}'...")
    print_progress("generating_html", "AI 正在美化格式並生成 HTML 報告...")
    prompt = HTML_GENERATION_PROMPT.format(
        video_title_for_html=video_title,
        summary_text_for_html=summary_text,
        transcript_text_for_html=transcript_text
    )
    try:
        model = genai_module.GenerativeModel(model_api_name)
        response = model.generate_content(prompt, request_options={'timeout': 1800})
        generated_html = response.text

        if generated_html.strip().startswith("```html"):
            generated_html = generated_html.strip()[7:]
        if generated_html.strip().endswith("```"):
            generated_html = generated_html.strip()[:-3]

        doctype_pos = generated_html.lower().find("<!doctype html>")
        if doctype_pos != -1:
            generated_html = generated_html[doctype_pos:]

        log.info("✅ Successfully generated HTML report.")
        print_progress("html_generated", "HTML 報告生成完畢。")
        return generated_html.strip()
    except Exception as e:
        log.critical(f"🔴 Failed to generate HTML report from Gemini: {e}", exc_info=True)
        raise

def process_audio_file(audio_path: Path, model: str, video_title: str, output_dir: Path):
    """
    完整的處理流程：上傳、分析、生成報告、轉換為 PDF、儲存、清理。
    """
    #延遲導入，使其只在需要時才導入
    try:
        import google.generativeai as genai
        from weasyprint import HTML
    except ImportError:
        log.critical("🔴 Necessary libraries (google-generativeai, WeasyPrint) not installed.")
        raise

    # 1. 設定 API 金鑰
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

    gemini_file_resource = None
    try:
        # 2. 上傳檔案
        gemini_file_resource = upload_to_gemini(genai, audio_path, audio_path.name)

        # 3. 取得摘要與逐字稿
        summary, transcript = get_summary_and_transcript(genai, gemini_file_resource, model, video_title, audio_path.name)

        # 4. 生成 HTML 報告內容 (仍在記憶體中)
        html_content = generate_html_report(genai, summary, transcript, model, video_title)

        # 5. 將 HTML 轉換並儲存為 PDF
        sanitized_title = sanitize_filename(video_title)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        pdf_filename = f"{sanitized_title}_{timestamp}_AI_Report.pdf"
        pdf_path = output_dir / pdf_filename

        log.info(f"📄 Converting HTML to PDF and saving to: {pdf_path}")
        print_progress("generating_pdf", "正在將報告轉換為 PDF...")
        HTML(string=html_content, base_url=str(output_dir)).write_pdf(pdf_path)
        log.info(f"✅ PDF report saved successfully.")

        # 6. 輸出最終結果
        final_result = {
            "type": "result",
            "status": "completed",
            "pdf_report_path": str(pdf_path), # 回傳 PDF 路徑
            "video_title": video_title
        }
        print(json.dumps(final_result), flush=True)

    finally:
        # 7. 清理 Gemini 雲端檔案
        if gemini_file_resource:
            log.info(f"🗑️ Cleaning up Gemini file: {gemini_file_resource.name}")
            try:
                # 增加重試機制
                for attempt in range(3):
                    try:
                        genai.delete_file(gemini_file_resource.name)
                        log.info("✅ Cleanup successful.")
                        break
                    except Exception as e_del:
                        log.warning(f"Attempt {attempt+1} to delete file failed: {e_del}")
                        if attempt < 2:
                            time.sleep(2)
                        else:
                            raise
            except Exception as e:
                log.error(f"🔴 Failed to clean up Gemini file '{gemini_file_resource.name}' after retries: {e}")


def main():
    parser = argparse.ArgumentParser(description="Gemini AI 處理工具。接收音訊檔案並生成分析報告。")
    parser.add_argument("--audio-file", type=str, required=True, help="要處理的音訊檔案路徑。")
    parser.add_argument("--model", type=str, required=True, help="要使用的 Gemini 模型 API 名稱。")
    parser.add_argument("--video-title", type=str, required=True, help="原始影片標題，用於提示詞。")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存生成報告的目錄。")
    args = parser.parse_args()

    audio_path = Path(args.audio_file)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        log.critical(f"Input audio file not found: {audio_path}")
        print(json.dumps({"type": "result", "status": "failed", "error": f"Input file not found: {audio_path}"}), flush=True)
        sys.exit(1)

    try:
        process_audio_file(audio_path, args.model, args.video_title, output_path)
    except Exception as e:
        log.critical(f"An error occurred in the main processing flow: {e}", exc_info=True)
        print(json.dumps({"type": "result", "status": "failed", "error": str(e)}), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
