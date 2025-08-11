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

# --- 提示詞管理 ---
# 取得此檔案所在的目錄，並建立 prompts.json 的路徑
PROMPTS_FILE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "default_prompts.json"

def load_prompts() -> dict:
    """從 prompts/default_prompts.json 載入所有提示詞。"""
    try:
        with open(PROMPTS_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.critical(f"🔴 無法載入或解析提示詞檔案: {PROMPTS_FILE_PATH}。錯誤: {e}", exc_info=True)
        # 在無法載入提示詞時，系統無法運作，應直接退出
        sys.exit(1)

# 在模組載入時就讀取所有提示詞
ALL_PROMPTS = load_prompts()


import google.generativeai as genai

# --- 核心 Gemini 處理函式 ---

def list_models():
    """列出可用的 Gemini 模型並以 JSON 格式輸出。"""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)

        models_list = []
        for m in genai.list_models():
            # 我們只關心支援 'generateContent' 且可用於 'models/' 的模型
            if 'generateContent' in m.supported_generation_methods:
                # 簡化輸出，只包含名稱和顯示名稱
                 models_list.append({
                     "id": m.name,
                     "name": m.display_name
                 })
        print(json.dumps(models_list), flush=True)
    except Exception as e:
        log.critical(f"🔴 Failed to list models: {e}", exc_info=True)
        # 將錯誤訊息輸出到 stderr，以便父程序擷取
        print(f"Error listing models: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

def validate_key():
    """
    僅驗證 API 金鑰的有效性。
    透過一個輕量級的操作（如列出模型）來實現。
    如果成功，以 exit code 0 退出。
    如果失敗，以 non-zero exit code 退出，並在 stderr 中提供錯誤訊息。
    """
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")
        genai.configure(api_key=api_key)

        # list_models 是一個相對輕量級的驗證操作
        genai.list_models()
        log.info("✅ API key validation successful.")
        sys.exit(0)
    except Exception as e:
        # 將具體的錯誤訊息輸出到 stderr
        # Google API 錯誤通常有自己的詳細描述
        print(f"API key not valid. Reason: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


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
    prompt = ALL_PROMPTS['get_summary_and_transcript'].format(original_filename=original_filename, video_title=video_title)
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
    prompt = ALL_PROMPTS['format_as_html'].format(
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

def process_audio_file(audio_path: Path, model: str, video_title: str, output_dir: Path, tasks: str, output_format: str):
    """
    全新的彈性處理流程，根據傳入的 tasks 和 output_format 執行操作。
    """
    # 延遲導入，使其只在需要時才導入
    try:
        import google.generativeai as genai
    except ImportError:
        log.critical("🔴 Necessary library (google-generativeai) not installed.")
        raise

    # 1. 設定 API 金鑰
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

    task_list = [t.strip() for t in tasks.lower().split(',') if t.strip()]
    results = {}  # 用於儲存各個任務的結果

    gemini_file_resource = None
    try:
        # 2. 上傳檔案 (所有任務都需要)
        gemini_file_resource = upload_to_gemini(genai, audio_path, audio_path.name)
        model_instance = genai.GenerativeModel(model)

        # 3. 執行 AI 任務
        # 為了效率，如果同時需要摘要和逐字稿，使用單一 prompt
        if "summary" in task_list and "transcript" in task_list:
            log.info("執行任務: 摘要與逐字稿 (合併執行)")
            summary, transcript = get_summary_and_transcript(genai, gemini_file_resource, model, video_title, audio_path.name)
            results['summary'] = summary
            results['transcript'] = transcript
        else:
            if "summary" in task_list:
                log.info("執行任務: 僅摘要")
                prompt = ALL_PROMPTS['get_summary_only'].format(original_filename=audio_path.name, video_title=video_title)
                response = model_instance.generate_content([prompt, gemini_file_resource], request_options={'timeout': 1800})
                results['summary'] = response.text.strip()
                log.info("✅ 摘要完成")

            if "transcript" in task_list:
                log.info("執行任務: 僅逐字稿")
                prompt = ALL_PROMPTS['get_transcript_only'].format(original_filename=audio_path.name, video_title=video_title)
                response = model_instance.generate_content([prompt, gemini_file_resource], request_options={'timeout': 3600})
                results['transcript'] = response.text.strip()
                log.info("✅ 逐字稿完成")

        if "translate" in task_list:
            log.info("執行任務: 翻譯")
            # 優先翻譯逐字稿，如果沒有，則翻譯摘要
            text_to_translate = results.get('transcript', results.get('summary', ''))
            if text_to_translate:
                prompt = ALL_PROMPTS['translate_text'].format(text_to_translate=text_to_translate)
                response = model_instance.generate_content(prompt, request_options={'timeout': 1800})
                results['translation'] = response.text.strip()
                log.info("✅ 翻譯完成")
            else:
                log.warning("⚠️ 無法執行翻譯，因為沒有可供翻譯的內容。")

        # 4. 根據輸出格式，組合並儲存檔案
        sanitized_title = sanitize_filename(video_title)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        final_filename_base = f"{sanitized_title}_{timestamp}_AI_Report"

        output_path = None
        if output_format == 'html':
            log.info("生成 HTML 格式報告...")
            # 確保即使只有部分內容，也能生成報告
            summary_content = results.get('summary', '無摘要')
            transcript_content = results.get('transcript', '無逐字稿')
            html_content = generate_html_report(genai, summary_content, transcript_content, model, video_title)

            output_path = output_dir / f"{final_filename_base}.html"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            log.info(f"✅ HTML 報告已儲存: {output_path}")

        elif output_format == 'txt':
            log.info("生成 TXT 格式報告...")
            output_content = f"報告標題: {video_title}\n\n"
            if 'summary' in results:
                output_content += f"--- 重點摘要 ---\n{results['summary']}\n\n"
            if 'transcript' in results:
                output_content += f"--- 詳細逐字稿 ---\n{results['transcript']}\n\n"
            if 'translation' in results:
                output_content += f"--- 英文翻譯 ---\n{results['translation']}\n\n"

            output_path = output_dir / f"{final_filename_base}.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
            log.info(f"✅ TXT 報告已儲存: {output_path}")
        else:
             raise ValueError(f"不支援的輸出格式: {output_format}")

        # 5. 輸出最終結果
        final_result = {
            "type": "result",
            "status": "completed",
            "output_path": str(output_path), # 回傳最終生成的檔案路徑
            "video_title": video_title
        }
        print(json.dumps(final_result), flush=True)

    finally:
        # 6. 清理 Gemini 雲端檔案
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
    parser = argparse.ArgumentParser(description="Gemini AI 處理工具。")
    parser.add_argument(
        "--command",
        type=str,
        default="process",
        choices=["process", "list_models", "validate_key"],
        help="要執行的操作。"
    )
    # 根據指令，動態決定其他參數是否為必需
    # 我們先解析一次，看看指令是什麼
    args, remaining_argv = parser.parse_known_args()

    if args.command == "list_models":
        list_models()
        return

    if args.command == "validate_key":
        validate_key()
        return

    # 如果是 'process' 指令，則需要其他參數
    if args.command == "process":
        process_parser = argparse.ArgumentParser()
        process_parser.add_argument("--command", type=str, help=argparse.SUPPRESS) # 忽略已解析的 command
        process_parser.add_argument("--audio-file", type=str, required=True, help="要處理的音訊檔案路徑。")
        process_parser.add_argument("--model", type=str, required=True, help="要使用的 Gemini 模型 API 名稱。")
        process_parser.add_argument("--video-title", type=str, required=True, help="原始影片標題，用於提示詞。")
        process_parser.add_argument("--output-dir", type=str, required=True, help="儲存生成報告的目錄。")
        # --- 新增的彈性參數 ---
        process_parser.add_argument("--tasks", type=str, default="summary,transcript", help="要執行的任務列表，以逗號分隔。例如：'summary,transcript,translate'")
        process_parser.add_argument("--output-format", type=str, default="html", choices=["html", "txt"], help="最終輸出的檔案格式。")


        process_args = process_parser.parse_args(remaining_argv)

        audio_path = Path(process_args.audio_file)
        output_path = Path(process_args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not audio_path.exists():
            log.critical(f"Input audio file not found: {audio_path}")
            print(json.dumps({"type": "result", "status": "failed", "error": f"Input file not found: {audio_path}"}), flush=True)
            sys.exit(1)

        try:
            # 將新的參數傳遞給 process_audio_file
            process_audio_file(
                audio_path=audio_path,
                model=process_args.model,
                video_title=process_args.video_title,
                output_dir=output_path,
                tasks=process_args.tasks,
                output_format=process_args.output_format
            )
        except Exception as e:
            log.critical(f"An error occurred in the main processing flow: {e}", exc_info=True)
            print(json.dumps({"type": "result", "status": "failed", "error": str(e)}), flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
