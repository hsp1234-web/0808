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

# --- 提示詞載入 ---
PROMPTS = {}
try:
    # 建立一個相對於目前檔案位置的路徑
    prompts_path = Path(__file__).resolve().parent.parent / "prompts" / "default_prompts.json"
    with open(prompts_path, 'r', encoding='utf-8') as f:
        PROMPTS = json.load(f)
    log.info(f"✅ 成功從 {prompts_path} 載入提示詞。")
except (FileNotFoundError, json.JSONDecodeError) as e:
    log.critical(f"🔴 無法載入提示詞檔案，請檢查 prompts/default_prompts.json 是否存在且格式正確。錯誤: {e}")
    # 在無法載入提示詞的嚴重情況下，程式無法繼續執行
    sys.exit(1)


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

def get_summary(genai_module, gemini_file_resource, model_api_name: str, video_title: str):
    """使用 Gemini 模型生成重點摘要。"""
    model = genai_module.GenerativeModel(model_api_name)
    log.info(f"🤖 Requesting summary from model '{model_api_name}'...")
    print_progress("generating_summary", "AI 正在生成重點摘要...")
    summary_prompt = PROMPTS['task_prompts']['summary']['prompt'].format(video_title=video_title)
    try:
        summary_response = model.generate_content([summary_prompt, gemini_file_resource], request_options={'timeout': 1800})
        summary_text = summary_response.text
        log.info("✅ Successfully generated summary.")
        return summary_text
    except Exception as e:
        log.error(f"🔴 Failed to get summary from Gemini: {e}", exc_info=True)
        return "生成重點摘要時發生錯誤。"

def get_transcript(genai_module, gemini_file_resource, model_api_name: str, video_title: str):
    """使用 Gemini 模型生成詳細逐字稿。"""
    model = genai_module.GenerativeModel(model_api_name)
    log.info(f"🤖 Requesting transcript from model '{model_api_name}'...")
    print_progress("generating_transcript", "AI 正在生成詳細逐字稿...")
    transcript_prompt = PROMPTS['task_prompts']['transcript']['prompt'].format(video_title=video_title)
    try:
        transcript_response = model.generate_content([transcript_prompt, gemini_file_resource], request_options={'timeout': 3600})
        transcript_text = transcript_response.text
        log.info("✅ Successfully generated transcript.")
        return transcript_text
    except Exception as e:
        log.error(f"🔴 Failed to get transcript from Gemini: {e}", exc_info=True)
        return "生成詳細逐字稿時發生錯誤。"

def generate_html_report(genai_module, model_api_name: str, video_title: str, **kwargs):
    """使用 Gemini 模型，根據提供的內容生成 HTML 報告。"""
    log.info(f"🎨 Requesting HTML report from model '{model_api_name}'...")
    print_progress("generating_html", "AI 正在美化格式並生成 HTML 報告...")

    # 從 kwargs 獲取內容，若無則提供預設值
    summary_text = kwargs.get('summary', '（未要求產生摘要）')
    transcript_text = kwargs.get('transcript', '（未要求產生逐字稿）')

    prompt = PROMPTS['format_prompts']['html_report']['prompt'].format(
        video_title_for_html=video_title,
        summary_text_for_html=summary_text,
        transcript_text_for_html=transcript_text
    )
    try:
        model = genai_module.GenerativeModel(model_api_name)
        response = model.generate_content(prompt, request_options={'timeout': 1800})
        generated_html = response.text

        # 清理 AI 可能額外添加的 markdown 標記
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

def process_audio_file(audio_path: Path, model: str, video_title: str, output_dir: Path, tasks: list, output_format: str):
    """
    更具彈性的處理流程：根據指定的任務和格式執行。
    """
    # 延遲導入，使其只在需要時才導入
    try:
        import google.generativeai as genai
    except ImportError:
        log.critical("🔴 Necessary library 'google-generativeai' not installed.")
        raise

    # 1. 設定 API 金鑰
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)

    gemini_file_resource = None
    try:
        # 2. 上傳檔案 (所有任務都需要)
        gemini_file_resource = upload_to_gemini(genai, audio_path, audio_path.name)

        # 3. 根據 `tasks` 列表執行 AI 任務
        task_results = {}
        if 'summary' in tasks:
            task_results['summary'] = get_summary(genai, gemini_file_resource, model, video_title)
        if 'transcript' in tasks:
            task_results['transcript'] = get_transcript(genai, gemini_file_resource, model, video_title)
        # 未來可以在此處擴充其他任務，例如 'translation'

        # 4. 根據 `output_format` 格式化並儲存結果
        sanitized_title = sanitize_filename(video_title)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        base_filename = f"{sanitized_title}_{timestamp}_AI_Report"

        output_path = None
        result_key = "output_path"

        if output_format == 'html':
            log.info("🖌️ Formatting output as HTML report...")
            html_content = generate_html_report(genai, model, video_title, **task_results)
            output_path = output_dir / f"{base_filename}.html"
            result_key = "html_report_path"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            log.info(f"✅ HTML report saved to: {output_path}")

        elif output_format == 'txt':
            log.info("✍️ Formatting output as plain text file...")
            # 建立一個簡單的純文字報告
            txt_content = []
            txt_content.append(f"# {video_title}\n")
            if 'summary' in task_results:
                txt_content.append("## 重點摘要\n")
                txt_content.append(task_results['summary'])
                txt_content.append("\n---\n")
            if 'transcript' in task_results:
                txt_content.append("## 詳細逐字稿\n")
                txt_content.append(task_results['transcript'])

            full_txt_content = "\n".join(txt_content)
            output_path = output_dir / f"{base_filename}.txt"
            result_key = "text_file_path"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_txt_content)
            log.info(f"✅ Text file saved to: {output_path}")

        else:
            raise ValueError(f"不支援的輸出格式: {output_format}")

        # 5. 輸出最終結果
        final_result = {
            "type": "result",
            "status": "completed",
            result_key: str(output_path),
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
    parser = argparse.ArgumentParser(description="Gemini AI 處理工具 v2。")
    parser.add_argument(
        "--command",
        type=str,
        default="process",
        choices=["process", "list_models", "validate_key"],
        help="要執行的操作。"
    )
    args, remaining_argv = parser.parse_known_args()

    if args.command == "list_models":
        list_models()
        return
    if args.command == "validate_key":
        validate_key()
        return

    if args.command == "process":
        process_parser = argparse.ArgumentParser()
        process_parser.add_argument("--audio-file", type=str, required=True, help="要處理的音訊檔案路徑。")
        process_parser.add_argument("--model", type=str, required=True, help="要使用的 Gemini 模型 API 名稱。")
        process_parser.add_argument("--video-title", type=str, required=True, help="原始影片標題，用於提示詞。")
        process_parser.add_argument("--output-dir", type=str, required=True, help="儲存生成報告的目錄。")
        process_parser.add_argument("--tasks", type=str, default="summary,transcript", help="要執行的任務列表，以逗號分隔 (例如 'summary,transcript')。")
        process_parser.add_argument("--format", type=str, default="html", choices=['html', 'txt'], help="最終輸出的檔案格式。")

        process_args = process_parser.parse_args(remaining_argv)

        audio_path = Path(process_args.audio_file)
        output_path = Path(process_args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not audio_path.exists():
            log.critical(f"Input audio file not found: {audio_path}")
            print(json.dumps({"type": "result", "status": "failed", "error": f"Input file not found: {audio_path}"}), flush=True)
            sys.exit(1)

        # 將 tasks 字串轉換為列表
        tasks_list = [task.strip() for task in process_args.tasks.split(',')]

        try:
            process_audio_file(
                audio_path,
                process_args.model,
                process_args.video_title,
                output_path,
                tasks=tasks_list,
                output_format=process_args.format
            )
        except Exception as e:
            log.critical(f"An error occurred in the main processing flow: {e}", exc_info=True)
            print(json.dumps({"type": "result", "status": "failed", "error": str(e)}), flush=True)
            sys.exit(1)


if __name__ == "__main__":
    main()
