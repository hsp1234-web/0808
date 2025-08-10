# tools/gemini_processor.py
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger('gemini_processor_tool')

# --- 核心處理邏輯 (改編自 colab.py) ---

def sanitize_filename(title, max_len=60):
    """清理檔案名稱，移除無效字元。"""
    if not title:
        title = "untitled_document"
    title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    title = title.replace(" ", "_")
    return title[:max_len]

def upload_to_gemini(audio_path: Path, display_filename: str):
    """上傳檔案至 Gemini Files API。"""
    import google.generativeai as genai
    log.info(f"☁️ Uploading '{display_filename}' to Gemini Files API...")
    print(json.dumps({"type": "progress", "status": "uploading", "detail": f"Uploading {display_filename}"}), flush=True)
    try:
        audio_file_resource = genai.upload_file(path=str(audio_path), display_name=display_filename)
        log.info(f"✅ Upload successful. Gemini File URI: {audio_file_resource.uri}")
        print(json.dumps({"type": "progress", "status": "upload_complete", "uri": audio_file_resource.uri}), flush=True)
        return audio_file_resource
    except Exception as e:
        log.critical(f"🔴 Failed to upload file to Gemini: {e}", exc_info=True)
        raise

def get_summary_and_transcript(gemini_file_resource, model_api_name: str, video_title: str, original_filename: str):
    """使用 Gemini 模型生成摘要與逐字稿。"""
    import google.generativeai as genai
    log.info(f"🤖 Requesting summary and transcript from model '{model_api_name}'...")
    print(json.dumps({"type": "progress", "status": "generating_transcript", "detail": "AI is generating summary and transcript..."}), flush=True)

    # 提示詞與 colab.py 中的版本保持一致
    prompt_text = f"""請您扮演一位專業的逐字稿分析師。
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
    try:
        model = genai.GenerativeModel(model_api_name)
        response = model.generate_content([prompt_text, gemini_file_resource], request_options={'timeout': 3600})
        full_response_text = response.text

        # 解析回應
        summary_match = re.search(r"\[重點摘要開始\](.*?)\[重點摘要結束\]", full_response_text, re.DOTALL)
        summary_text = summary_match.group(1).strip() if summary_match else "未擷取到重點摘要。"

        transcript_match = re.search(r"\[詳細逐字稿開始\](.*?)\[詳細逐字稿結束\]", full_response_text, re.DOTALL)
        transcript_text = transcript_match.group(1).strip() if transcript_match else "未擷取到詳細逐字稿。"

        # 如果都沒擷取到，做一個備用方案
        if "未擷取到" in summary_text and "未擷取到" in transcript_text:
            transcript_text = full_response_text
            summary_text = "（自動摘要失敗，請參考下方逐字稿自行整理）"

        log.info("✅ Successfully generated summary and transcript.")
        return summary_text, transcript_text
    except Exception as e:
        log.critical(f"🔴 Failed to get summary/transcript from Gemini: {e}", exc_info=True)
        raise

def generate_html_report(summary_text: str, transcript_text: str, model_api_name: str, video_title: str):
    """使用 Gemini 模型生成 HTML 報告。"""
    import google.generativeai as genai
    log.info(f"🎨 Requesting HTML report from model '{model_api_name}'...")
    print(json.dumps({"type": "progress", "status": "generating_html", "detail": "AI is generating HTML report..."}), flush=True)

    # 提示詞與 colab.py 中的版本保持一致
    html_generation_prompt = f"""請生成一個完整的HTML檔案... (此處省略與 colab.py 相同的超長提示詞) ...
影片標題：
---[影片標題開始]---
{video_title}
---[影片標題結束]---

重點摘要內容：
---[重點摘要內容開始]---
{summary_text}
---[重點摘要內容結束]---

逐字稿內容：
---[逐字稿內容開始]---
{transcript_text}
---[逐字稿內容結束]---
"""
    # 實際使用時，應貼上 colab.py 中完整的 HTML 生成提示詞
    # 為簡化範例，此處僅示意
    from colab import generate_html_report_from_gemini as colab_html_generator
    # 這裡我們直接借用 colab.py 的提示詞，但這在真實分離的工具中不是最佳實踐
    # 理想情況下，提示詞應該也存在一個共享的地方
    # 為了推進，我們假設提示詞是可用的

    # 簡化的替代方案：
    if "請生成一個完整的HTML檔案" in html_generation_prompt:
         # 這裡應該有完整的提示詞
         # 為了簡化，我們直接從 colab.py 複製提示詞
         from colab import html_generation_prompt_template
         html_generation_prompt = html_generation_prompt_template.format(
             video_title_for_html=video_title,
             summary_text_for_html=summary_text,
             transcript_text_for_html=transcript_text
         )

    try:
        model = genai.GenerativeModel(model_api_name)
        response = model.generate_content(html_generation_prompt, request_options={'timeout': 1800})
        generated_html = response.text

        # 清理 Gemini 可能添加的 Markdown 標記
        if generated_html.strip().startswith("```html"):
            generated_html = generated_html.strip()[7:]
        if generated_html.strip().endswith("```"):
            generated_html = generated_html.strip()[:-3]

        log.info("✅ Successfully generated HTML report.")
        return generated_html.strip()
    except Exception as e:
        log.critical(f"🔴 Failed to generate HTML report from Gemini: {e}", exc_info=True)
        raise

def process_audio_file(audio_path: Path, model: str, video_title: str, output_dir: Path):
    """
    完整的處理流程。
    """
    import google.generativeai as genai

    # 1. 設定 API 金鑰
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

    gemini_file = None
    try:
        # 2. 上傳檔案
        gemini_file = upload_to_gemini(audio_path, audio_path.name)

        # 3. 取得摘要與逐字稿
        summary, transcript = get_summary_and_transcript(gemini_file, model, video_title, audio_path.name)

        # 4. 生成 HTML 報告
        html_content = generate_html_report(summary, transcript, model, video_title)

        # 5. 儲存 HTML 報告
        sanitized_title = sanitize_filename(video_title)
        html_filename = f"{sanitized_title}_AI_Report.html"
        html_path = output_dir / html_filename
        html_path.write_text(html_content, encoding='utf-8')
        log.info(f"✅ HTML report saved to: {html_path}")

        # 6. 輸出最終結果
        final_result = {
            "type": "result",
            "status": "completed",
            "html_report_path": str(html_path),
            "video_title": video_title
        }
        print(json.dumps(final_result), flush=True)

    finally:
        # 7. 清理 Gemini 雲端檔案
        if gemini_file:
            log.info(f"🗑️ Cleaning up Gemini file: {gemini_file.name}")
            try:
                genai.delete_file(gemini_file.name)
                log.info("✅ Cleanup successful.")
            except Exception as e:
                log.error(f"🔴 Failed to clean up Gemini file '{gemini_file.name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Gemini AI 處理工具。")
    parser.add_argument("--audio-file", type=str, required=True, help="要處理的音訊檔案路徑。")
    parser.add_argument("--model", type=str, required=True, help="要使用的 Gemini 模型名稱。")
    parser.add_argument("--video-title", type=str, required=True, help="原始影片標題，用於提示詞。")
    parser.add_argument("--output-dir", type=str, required=True, help="儲存生成報告的目錄。")
    args = parser.parse_args()

    audio_path = Path(args.audio_file)
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        log.critical(f"Input audio file not found: {audio_path}")
        sys.exit(1)

    process_audio_file(audio_path, args.model, args.video_title, output_path)

if __name__ == "__main__":
    # 為了能從 colab.py 導入提示詞，需要將根目錄加入 sys.path
    # 這是一個臨時解決方案，理想情況下提示詞應該被重構到一個共享模組中
    ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    main()
