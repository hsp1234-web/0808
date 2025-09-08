import os
import logging
import json
import time
import threading
from collections import deque
from typing import List, Optional, Tuple, Dict, Any

# 嘗試匯入 genai，如果失敗也不會中斷程式
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    from PIL import Image
except ImportError:
    genai = None
    GenerationConfig = None
    Image = None

# --- API 管理器 (從 Colab 腳本移植並改造) ---
class ApiKey:
    """簡單的 API 金鑰容器"""
    def __init__(self, key_value: str, name: str):
        self.key = key_value
        self.name = name

class GeminiManager:
    """
    管理與 Google Gemini API 的所有互動，包括金鑰輪換、重試機制和提示詞工程。
    """
    def __init__(self, api_keys: List[Dict[str, str]], timeout: int = 180, max_retries: int = 3):
        if not api_keys:
            raise ValueError("API 金鑰列表不可為空。")

        self.key_pool = deque([ApiKey(key_value=k['value'], name=k['name']) for k in api_keys])
        self.timeout = timeout
        self.max_retries = max_retries
        self._lock = threading.Lock()
        logging.info(f"Gemini 管理器已初始化，共載入 {len(self.key_pool)} 組 API 金鑰。")

    def _get_key(self) -> ApiKey:
        with self._lock:
            key = self.key_pool[0]
            self.key_pool.rotate(-1)
            return key

    def _api_call_wrapper(self, task_name: str, model_name: str, prompt_content: List[Any], response_parser):
        if not genai or not GenerationConfig:
            logging.error("google.generativeai 套件未安裝或不完整。無法執行 API 呼叫。")
            return None, "google.generativeai not installed", "N/A"

        api_key = self._get_key()
        last_error = None

        for attempt in range(self.max_retries):
            tag = f"{task_name}-{api_key.name}"
            logging.info(f"[{tag}] 正在執行 API 請求 (使用模型: {model_name}, 第 {attempt + 1}/{self.max_retries} 次嘗試)...")
            try:
                genai.configure(api_key=api_key.key)
                model = genai.GenerativeModel(model_name)

                response = model.generate_content(
                    prompt_content,
                    generation_config=GenerationConfig(response_mime_type="application/json"),
                    request_options={'timeout': self.timeout}
                )
                raw_text = response.text

                if not raw_text:
                    raise ValueError("API 回傳空內容")

                if raw_text.strip().startswith("```json"):
                    raw_text = raw_text.strip()[7:-3].strip()

                parsed_json = json.loads(raw_text)
                return response_parser(parsed_json), None, api_key.name

            except Exception as e:
                last_error = e
                last_error_str = f"{type(e).__name__}: {e}"
                retryable_errors = ["500", "503", "timed out", "deadline", "aborted", "reset", "quota"]

                if any(s in last_error_str.lower() for s in retryable_errors) and attempt < self.max_retries - 1:
                    logging.warning(f"[{tag}] 請求失敗 (可重試)，{2**(attempt+1)} 秒後重試...")
                    time.sleep(2**(attempt+1))
                    continue
                break

        logging.error(f"[{tag}] 經過 {self.max_retries} 次嘗試後，API 請求最終失敗: {last_error}")
        return None, last_error, api_key.name

    def analyze_text(self, text_content: str, model_name: str = "gemini-1.5-flash-latest") -> Optional[Dict]:
        prompt = f"""
        你是一位專業的內容分析師。請閱讀以下文章，並以 JSON 格式回傳包含以下兩個鍵的物件：
        1. `summary` (string): 對文章內容的簡短摘要。
        2. `keywords` (list of strings): 從文章中提取的 3-5 個核心關鍵字。

        文章內容如下：
        ---
        {text_content}
        ---
        請直接回傳 JSON 物件，不要包含任何額外的解釋或 Markdown 標記。
        """

        result, _, _ = self._api_call_wrapper(
            task_name="AnalyzeText",
            model_name=model_name,
            prompt_content=[prompt],
            response_parser=lambda r: r
        )
        return result

    def describe_image(self, image_path: str, model_name: str = "gemini-1.5-flash-latest") -> Optional[Dict]:
        """
        描述一張圖片的內容。
        修正：將預設模型從 pro 改為 flash 以避免免費額度問題。
        """
        if not Image:
            logging.error("Pillow 套件未安裝，無法處理圖片。")
            return None

        try:
            img = Image.open(image_path)
        except Exception as e:
            logging.error(f"無法開啟圖片檔案 '{image_path}': {e}")
            return None

        prompt = """
        你是一位圖像分析專家。請描述這張圖片的內容。如果它是一張圖表，請說明它的類型以及它可能在傳達的資訊。
        請以 JSON 格式回傳包含以下兩個鍵的物件：
        1. `description` (string): 對圖片內容的詳細描述。
        2. `chart_type` (string): 如果是圖表，請指出其類型（例如 '長條圖', '折線圖', '圓餅圖'）。如果不是圖表，則回傳 '非圖表'。
        """

        result, _, _ = self._api_call_wrapper(
            task_name="DescribeImage",
            model_name=model_name,
            prompt_content=[prompt, img],
            response_parser=lambda r: r
        )
        return result
