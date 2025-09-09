# src/tools/gemini_analyzer.py
"""
一個獨立的模組，專門負責與 Gemini API 互動以進行 AI 分析。
"""
import logging
import re
import json
from pathlib import Path
from typing import Tuple, Any, Dict, List

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

log = logging.getLogger(__name__)

# --- 自訂例外 ---
class AnalyzerException(Exception):
    """AI 分析過程中發生的自訂錯誤。"""
    pass

# --- 提示詞管理 ---
PROMPTS_FILE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "default_prompts.json"
ALL_PROMPTS = {}

def load_prompts() -> Dict[str, str]:
    """
    從 JSON 檔案載入並快取提示詞。
    :return: 一個包含所有提示詞的字典。
    :raises AnalyzerException: 如果檔案找不到或無法解析。
    """
    global ALL_PROMPTS
    if ALL_PROMPTS:
        return ALL_PROMPTS
    try:
        with open(PROMPTS_FILE_PATH, 'r', encoding='utf-8') as f:
            ALL_PROMPTS = json.load(f)
            return ALL_PROMPTS
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.critical(f"🔴 無法載入或解析提示詞檔案: {PROMPTS_FILE_PATH}。錯誤: {e}", exc_info=True)
        raise AnalyzerException(f"無法載入提示詞: {e}") from e

# --- 核心分析函式 ---

def _get_error_from_response(response: Any) -> str | None:
    """從 Gemini API 的回應中解析出錯誤訊息。"""
    try:
        if response.prompt_feedback.block_reason:
            return f"請求被 Gemini 安全設定阻擋，原因: {response.prompt_feedback.block_reason.name}"
        candidate = response.candidates[0]
        if candidate.finish_reason.name not in ("STOP", "MAX_TOKENS"):
            return f"內容生成異常終止，原因: {candidate.finish_reason.name}"
    except (AttributeError, IndexError):
        return None
    return None

def _generate_content(model: genai.GenerativeModel, prompt_parts: List[Any], request_options: Dict[str, Any] = None) -> Any:
    """
    對 genai.GenerativeModel.generate_content 的一個封裝，增加了錯誤處理。
    """
    try:
        log.info(f"正在向模型 '{model.model_name}' 發送請求...")
        response = model.generate_content(prompt_parts, request_options=request_options)

        # 檢查是否有立即的錯誤回饋
        error_message = _get_error_from_response(response)
        if error_message:
            raise AnalyzerException(error_message)

        log.info("✅ 模型成功生成內容。")
        return response
    except google_exceptions.GoogleAPICallError as e:
        log.error(f"🔴 呼叫 Gemini API 時發生錯誤: {e}")
        raise AnalyzerException(f"Gemini API 呼叫失敗: {e}") from e
    except Exception as e:
        log.error(f"🔴 內容生成過程中發生未預期的錯誤: {e}", exc_info=True)
        raise AnalyzerException(f"內容生成時發生未預期錯誤: {e}") from e


def get_summary_and_transcript(
    model: genai.GenerativeModel,
    gemini_file_resource: Any,
    video_title: str,
    original_filename: str
) -> Tuple[str, str, int]:
    """
    從 Gemini 模型獲取音訊的摘要和逐字稿。

    :return: 一個包含 (摘要, 逐字稿, token用量) 的元組。
    :raises AnalyzerException: 如果分析失敗。
    """
    prompts = load_prompts()
    prompt = prompts['get_summary_and_transcript'].format(
        original_filename=original_filename,
        video_title=video_title
    )

    response = _generate_content(model, [prompt, gemini_file_resource])

    full_response_text = response.text
    summary_match = re.search(r"\[重點摘要開始\](.*?)\[重點摘要結束\]", full_response_text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else "未擷取到重點摘要。"

    transcript_match = re.search(r"\[詳細逐字稿開始\](.*?)\[詳細逐字稿結束\]", full_response_text, re.DOTALL)
    transcript = transcript_match.group(1).strip() if transcript_match else "未擷取到詳細逐字稿。"

    # 如果兩者都沒抓到，可能是模型沒按規定格式回傳，直接用全文當逐字稿
    if "未擷取到" in summary and "未擷取到" in transcript:
        transcript = full_response_text
        summary = "（自動摘要失敗，請參考下方逐字稿自行整理）"

    tokens_used = response.usage_metadata.total_token_count or 0

    return summary, transcript, tokens_used


def generate_html_report(
    model: genai.GenerativeModel,
    summary: str,
    transcript: str,
    video_title: str
) -> Tuple[str, int]:
    """
    使用 Gemini 模型將文字內容格式化為 HTML 報告。

    :return: 一個包含 (HTML內容, token用量) 的元組。
    :raises AnalyzerException: 如果分析失敗。
    """
    prompts = load_prompts()
    prompt = prompts['format_as_html'].format(
        video_title_for_html=video_title,
        summary_text_for_html=summary,
        transcript_text_for_html=transcript
    )

    response = _generate_content(model, [prompt])

    html_content = response.text
    # 清理模型可能回傳的 markdown 標籤
    if html_content.strip().startswith("```html"):
        html_content = html_content.strip()[7:]
    if html_content.strip().endswith("```"):
        html_content = html_content.strip()[:-3]

    # 確保文件以 <!doctype html> 開頭
    doctype_pos = html_content.lower().find("<!doctype html>")
    if doctype_pos != -1:
        html_content = html_content[doctype_pos:]

    tokens_used = response.usage_metadata.total_token_count or 0

    return html_content.strip(), tokens_used
