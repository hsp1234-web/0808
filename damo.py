# @title 1. 環境設定與套件安裝
# -*- coding: utf-8 -*-
# ==============================================================================
# Part 1: 環境自動設定
# ==============================================================================
import os
import subprocess
import sys
import time
import re
from IPython.display import display, HTML, Javascript, Image as IPImage
import ipywidgets as widgets
from google.colab import files as colab_files
import shutil # 用於檔案操作
from datetime import datetime
import html # 用於HTML內容轉義

# --- 檢查並安裝 Python 套件 ---
def install_python_packages():
    """檢查並安裝所需的 Python 套件。"""
    packages = {
        "pytubefix": "pytubefix",
        "ffmpeg-python": "ffmpeg-python",
        "google-generativeai": "google.generativeai",
        "pydub": "pydub"
    }
    installed_marker = "/tmp/.colab_integrated_yt_processor_py_packages_installed_v5" # 更新版本標記

    if not os.path.exists(installed_marker):
        print("首次執行或版本更新，正在檢查並安裝 Python 套件...")
        for pkg_name, import_name in packages.items():
            try:
                __import__(import_name)
                print(f"套件 {pkg_name} 已安裝。")
            except ImportError:
                print(f"正在安裝套件 {pkg_name}...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg_name])
                print(f"套件 {pkg_name} 安裝完成。")
        with open(installed_marker, 'w') as f:
            f.write('installed')
        print("所有必要的 Python 套件已準備就緒。\n")
    else:
        print("Python 套件已檢查，無需重複安裝。\n")

install_python_packages()

# --- 導入已安裝的套件 ---
try:
    from pytubefix import YouTube
    from pytubefix.exceptions import RegexMatchError, VideoUnavailable
    import ffmpeg
    import google.generativeai as genai
    from google.colab import userdata
    from pydub import AudioSegment
    import io
except ImportError as e:
    print(f"導入套件時發生錯誤，請重新啟動執行環境: {e}")
    raise

# --- 檢查並安裝 ffmpeg 工具 ---
def install_ffmpeg():
    """檢查系統是否已安裝 ffmpeg，如果沒有則嘗試安裝。"""
    ffmpeg_installed_marker = "/tmp/.colab_integrated_ffmpeg_installed_v5"
    if not os.path.exists(ffmpeg_installed_marker):
        print("首次執行或版本更新，正在檢查並安裝 ffmpeg 工具...")
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print("ffmpeg 已安裝。")
            with open(ffmpeg_installed_marker, 'w') as f:
                f.write('installed')
            print("ffmpeg 工具已準備就緒。\n")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ffmpeg 未安裝，正在嘗試安裝...")
            try:
                subprocess.run(["apt-get", "update", "-qq"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["apt-get", "install", "-y", "ffmpeg", "-qq"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("ffmpeg 安裝成功。")
                with open(ffmpeg_installed_marker, 'w') as f:
                    f.write('installed')
                print("ffmpeg 工具已準備就緒。\n")
                return True
            except Exception as e_ffmpeg:
                print(f"ffmpeg 安裝失敗: {e_ffmpeg}")
                return False
    else:
        print("ffmpeg 工具已檢查，無需重複安裝。\n")
    return True

ffmpeg_ready = install_ffmpeg()

if not ffmpeg_ready:
    display(HTML("<p style='color:red; font-weight:bold;'>警告：ffmpeg 工具未能成功初始化。部分音訊處理功能可能受限。</p>"))

# @title 2. API 金鑰與 Gemini 模型設定
# ==============================================================================
# Part 2: API 金鑰與 Gemini 模型相關設定
# ==============================================================================
API_KEY_CONFIGURED = False
try:
    GOOGLE_API_KEY = userdata.get('GOOGLE_API_KEY')
    if not GOOGLE_API_KEY:
        display(HTML("<p style='color:#FF6B6B; font-weight:bold;'>⚠️ GOOGLE_API_KEY 未在 Colab Secrets 中設定。請先設定！點擊左側鑰匙圖示設定。</p>"))
    else:
        genai.configure(api_key=GOOGLE_API_KEY)
        API_KEY_CONFIGURED = True
        print("🔑 Google API 金鑰設定成功！")
except Exception as e:
    print(f"🔴 設定 Google API 金鑰時發生錯誤：{e}")
    display(HTML("<p style='color:#FF6B6B; font-weight:bold;'>🔴 設定 API 金鑰失敗，請檢查 Secrets 設定。</p>"))

# --- 預定義模型中文介紹 (核心模型，使用繁體中文) ---
PREDEFINED_MODELS_DATA = {
    "models/gemini-1.5-flash-latest": {
        "dropdown_display_name": "Gemini 1.5 Flash Latest",
        "chinese_display_name": "Gemini 1.5 Flash 最新版",
        "chinese_summary_parenthesized": "（速度快、多功能、多模態、適用於多樣化任務擴展）",
        "chinese_input_output": "輸入：文字、音訊、圖片、影片 (建議查閱最新官方文件確認支援細節)；輸出：文字",
        "chinese_suitable_for": "適合用途：需要快速回應的多樣化任務、大規模應用程式、聊天機器人、內容摘要、音訊處理。",
        "original_description_from_api": "Alias that points to the most recent production (non-experimental) release of Gemini 1.5 Flash, our fast and versatile multimodal model for scaling across diverse tasks."
    },
    "models/gemini-1.5-pro-latest": {
        "dropdown_display_name": "Gemini 1.5 Pro Latest",
        "chinese_display_name": "Gemini 1.5 Pro 最新版",
        "chinese_summary_parenthesized": "（功能強大、大型上下文視窗、多模態、理解複雜情境）",
        "chinese_input_output": "輸入：文字、音訊、圖片、影片 (建議查閱最新官方文件確認支援細節)；輸出：文字",
        "chinese_suitable_for": "適合用途：複雜的推理任務、長篇內容理解與生成（最高達200萬符記）、多模態分析與應用。",
        "original_description_from_api": "Alias that points to the most recent production (non-experimental) release of Gemini 1.5 Pro, our mid-size multimodal model that supports up to 2 million tokens."
    },
     "models/gemini-pro": {
        "dropdown_display_name": "Gemini Pro (Text Only)",
        "chinese_display_name": "Gemini Pro 純文字版",
        "chinese_summary_parenthesized": "（優化的純文字生成與理解模型）",
        "chinese_input_output": "輸入：文字；輸出：文字",
        "chinese_suitable_for": "適合用途：純文字的問答、摘要、寫作、翻譯等任務。",
        "original_description_from_api": "Optimized for text-only prompts."
    }
}

# --- 模型瀏覽器相關 UI 與函式 ---
model_selector_dropdown = widgets.Dropdown(
    options=[("請稍候，正在載入模型列表...", None)],
    description='選擇模型:',
    disabled=True, style={'description_width': 'initial'}, layout={'width': 'max-content'}
)
model_details_html = widgets.HTML(value=f"<p style='color: #FCFCFC; font-style:italic;'>請從上方選擇一個模型以查看其介紹。</p>")
ALL_MODELS_CACHE = {}

def get_model_version_score(api_name_lower):
    score = 9999
    if "latest" in api_name_lower: score = 0
    elif "preview" in api_name_lower:
        score = 1000
        date_match = re.search(r'preview[_-](\d{2})[_-]?(\d{2})', api_name_lower)
        if date_match: score -= (int(date_match.group(1)) * 100 + int(date_match.group(2)))
        else: score += 100
    elif "-exp" in api_name_lower or "experimental" in api_name_lower: score = 2000
    else:
        num_version_match = re.search(r'-(\d[\d\.]*)$', api_name_lower.split('/')[-1])
        if num_version_match:
            try: score = 3000 - int(float(num_version_match.group(1).replace('-', '.')) * 100)
            except ValueError: score = 3500
    return score

def sort_models_for_dropdown_key(model_api_name):
    name_lower = model_api_name.lower()
    if "gemini-1.5-pro" in name_lower: priority_group = 0
    elif "gemini-1.5-flash" in name_lower: priority_group = 1
    elif "gemini-pro" in name_lower and "vision" not in name_lower : priority_group = 2
    elif "gemini" in name_lower: priority_group = 3
    elif "gemma" in name_lower: priority_group = 4
    else: priority_group = 5

    version_score = get_model_version_score(name_lower)
    main_version_num = 0.0
    main_version_match = re.search(r'(gemini|gemma)-(\d+\.\d+|\d+)', name_lower)
    if main_version_match:
        try: main_version_num = float(main_version_match.group(2))
        except ValueError: pass
    return (priority_group, -main_version_num, version_score, name_lower)


def populate_model_dropdown(status_output_widget_ref):
    if not API_KEY_CONFIGURED:
        model_selector_dropdown.options = [("API 金鑰未設定", None)]; model_selector_dropdown.disabled = True; return
    with status_output_widget_ref:
        status_output_widget_ref.clear_output(wait=True)
        print("🔄 正在查詢線上模型列表並與預定義列表合併...")

    live_models_from_api = {}
    try:
        for m_obj in genai.list_models():
            supported_methods = getattr(m_obj, 'supported_generation_methods', [])
            if 'generateContent' in supported_methods:
                live_models_from_api[m_obj.name] = m_obj
    except Exception as e:
        with status_output_widget_ref: print(f"🔴 查詢線上模型列表失敗: {e}")

    ALL_MODELS_CACHE.clear(); temp_dropdown_options = []
    for api_name, data in PREDEFINED_MODELS_DATA.items():
        display_name = data.get("dropdown_display_name", api_name.replace("models/", ""))
        temp_dropdown_options.append((display_name, api_name))
        ALL_MODELS_CACHE[api_name] = {"type": "predefined", "data": data}
        if api_name in live_models_from_api: del live_models_from_api[api_name]

    for api_name, model_obj in live_models_from_api.items():
        display_name_api = getattr(model_obj, 'displayName', None)
        if not display_name_api or not display_name_api.strip(): display_name_api = api_name.replace("models/", "")
        temp_dropdown_options.append((display_name_api, api_name))
        ALL_MODELS_CACHE[api_name] = {"type": "live_api", "data": model_obj}

    temp_dropdown_options.sort(key=lambda item_tuple: sort_models_for_dropdown_key(item_tuple[1]))

    if temp_dropdown_options:
        model_selector_dropdown.options = temp_dropdown_options
        model_selector_dropdown.disabled = False
        if model_selector_dropdown.options:
            model_selector_dropdown.value = temp_dropdown_options[0][1]
            on_model_selection_change({'new': model_selector_dropdown.value, 'type': 'change', 'name': 'value'})
        with status_output_widget_ref: print(f"✅ 模型列表載入並排序完成，共 {len(temp_dropdown_options)} 個模型可選。")
    else:
        model_selector_dropdown.options = [("未找到可用模型", None)]; model_selector_dropdown.disabled = True
        model_details_html.value = f"<p style='color: #FCFCFC; font-style:italic;'>未能載入任何模型資訊。</p>"
        with status_output_widget_ref: print("⚠️ 未找到任何可用模型。")

def display_model_introduction(api_name):
    font_color = "#FCFCFC"
    if not api_name or api_name not in ALL_MODELS_CACHE:
        model_details_html.value = f"<p style='color:{font_color}; font-style:italic;'>請選擇一個模型。</p>"; return

    model_info = ALL_MODELS_CACHE[api_name]
    html_output = f"<div style='padding: 10px; margin-top: 8px; font-family: \"Roboto\", Arial, sans-serif; line-height: 1.6; border-top: 1px solid #555; border-bottom: 1px solid #555; color: {font_color};'>"
    if model_info["type"] == "predefined":
        data = model_info["data"]
        title = data.get('chinese_display_name', 'N/A'); summary = data.get('chinese_summary_parenthesized', '')
        input_output = data.get('chinese_input_output', 'N/A'); suitable_for = data.get('chinese_suitable_for', 'N/A')
        html_output += f"<h4 style='margin-top:0; margin-bottom:8px; color: #E0E0E0;'>{title} <span style='font-weight:normal; color: {font_color};'>{summary}</span></h4>"
        html_output += f"<p style='margin-bottom:5px;'><strong style='font-weight:bold; color: #C0C0C0;'>輸入輸出能力：</strong>{input_output}</p>"
        html_output += f"<p style='margin-bottom:0;'><strong style='font-weight:bold; color: #C0C0C0;'>適合用途：</strong>{suitable_for}</p>"
    elif model_info["type"] == "live_api":
        model_obj = model_info["data"]
        display_name_api = getattr(model_obj, 'displayName', model_obj.name.replace("models/", ""))
        description_api = getattr(model_obj, 'description', "API 未提供描述。")
        description_html_formatted = html.escape(description_api).replace('\n', '<br>')
        version_api = getattr(model_obj, 'version', "N/A"); input_tokens_api = getattr(model_obj, 'input_token_limit', "N/A"); output_tokens_api = getattr(model_obj, 'output_token_limit', "N/A")
        html_output += f"<h4 style='margin-top:0; margin-bottom:8px; color: #E0E0E0;'>{display_name_api} (英文原始資訊)</h4>"
        html_output += f"<p style='margin-bottom:5px;'><strong style='font-weight:bold; color: #C0C0C0;'>描述 (Description)：</strong>{description_html_formatted}</p>"
        html_output += f"<p style='margin-bottom:5px;'><strong style='font-weight:bold; color: #C0C0C0;'>版本 (Version)：</strong>{version_api}</p>"
        html_output += f"<p style='margin-bottom:5px;'><strong style='font-weight:bold; color: #C0C0C0;'>輸入符記上限 (Input Token Limit)：</strong>{input_tokens_api}</p>"
        html_output += f"<p style='margin-bottom:0;'><strong style='font-weight:bold; color: #C0C0C0;'>輸出符記上限 (Output Token Limit)：</strong>{output_tokens_api}</p>"
        html_output += f"<p style='font-size:small; margin-top:10px; color: #AAA;'>API Name: {model_obj.name}</p>"
    html_output += "</div>"; model_details_html.value = html_output

def on_model_selection_change(change):
    selected_api_name = change.get('new')
    if selected_api_name: display_model_introduction(selected_api_name)

model_selector_dropdown.observe(on_model_selection_change, names='value')


# @title 3. 全域變數與輔助函式
# ==============================================================================
# Part 3: 全域變數與輔助函式
# ==============================================================================
DOWNLOAD_DIR = "/content/youtube_audio_outputs/"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_FILENAME_LENGTH_BASE = 60

def sanitize_filename(title, max_len=MAX_FILENAME_LENGTH_BASE):
    if not title: title = "untitled_audio"
    title = re.sub(r'[\\/*?:"<>|]', "_", title)
    title = title.replace(" ", "_")
    title = re.sub(r"_+", "_", title)
    title = title.strip('_')
    return title[:max_len]

def format_bytes(size_bytes):
    if size_bytes is None or size_bytes == 0: return "0 B"
    power = 1024; n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size_bytes >= power and n < len(power_labels) -1:
        size_bytes /= power; n += 1
    return f"{size_bytes:.2f} {power_labels[n]}"

def format_duration(seconds_total):
    if seconds_total is None: return "未知時長"
    seconds_total = int(seconds_total)
    hours = seconds_total // 3600
    minutes = (seconds_total % 3600) // 60
    seconds = seconds_total % 60
    if hours > 0: return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

current_video_info = {'title': None, 'sanitized_title': None, 'duration_sec': None}

# @title 4. YouTube 音訊下載函式
# ==============================================================================
# Part 4: YouTube 音訊下載
# ==============================================================================
_yt_dl_status_output_ref = None
_yt_dl_total_size = 0
_yt_dl_bytes_downloaded = 0
_yt_dl_start_time = 0

def on_yt_download_progress(stream, chunk, bytes_remaining):
    global _yt_dl_total_size, _yt_dl_bytes_downloaded, _yt_dl_start_time, _yt_dl_status_output_ref
    if _yt_dl_status_output_ref is None: return

    if _yt_dl_total_size == 0:
        _yt_dl_total_size = stream.filesize if stream.filesize else 0
        _yt_dl_bytes_downloaded = 0
        _yt_dl_start_time = time.time()

    if _yt_dl_total_size > 0:
        _yt_dl_bytes_downloaded = _yt_dl_total_size - bytes_remaining
        percentage = (_yt_dl_bytes_downloaded / _yt_dl_total_size) * 100
    else:
        _yt_dl_bytes_downloaded += len(chunk)
        percentage = 0

    elapsed_time = time.time() - _yt_dl_start_time
    speed = _yt_dl_bytes_downloaded / elapsed_time if elapsed_time > 0 else 0
    eta_str = "未知"

    if speed > 0 and _yt_dl_total_size > 0:
        eta = (_yt_dl_total_size - _yt_dl_bytes_downloaded) / speed
        eta_str = format_duration(eta)

    with _yt_dl_status_output_ref:
        _yt_dl_status_output_ref.clear_output(wait=True)
        progress_bar = f"[{'=' * int(percentage / 4)}{' ' * (25 - int(percentage / 4))}]" if _yt_dl_total_size > 0 else "[下載中...]"
        print(f"   ↳ 音訊下載進度: {percentage:.2f}% {progress_bar}" if _yt_dl_total_size > 0 else "   ↳ 音訊下載進度: [大小未知]")
        print(f"   已下載: {format_bytes(_yt_dl_bytes_downloaded)} / {format_bytes(_yt_dl_total_size) if _yt_dl_total_size > 0 else '未知總大小'}")
        print(f"   速度: {format_bytes(speed)}/s | 預計剩餘: {eta_str if _yt_dl_total_size > 0 else '未知'}")

def download_youtube_audio(youtube_url, status_output_widget):
    global current_video_info, _yt_dl_status_output_ref, _yt_dl_total_size, _yt_dl_bytes_downloaded, _yt_dl_start_time
    _yt_dl_status_output_ref = status_output_widget
    _yt_dl_total_size = 0; _yt_dl_bytes_downloaded = 0; _yt_dl_start_time = 0

    with status_output_widget:
        status_output_widget.clear_output(wait=True)
        print(f"🔗 正在連接 YouTube 並取得影片資訊: {youtube_url}")

    try:
        yt = YouTube(youtube_url, on_progress_callback=on_yt_download_progress)
        current_video_info['title'] = yt.title
        current_video_info['sanitized_title'] = sanitize_filename(yt.title)
        current_video_info['duration_sec'] = yt.length

        with status_output_widget:
            status_output_widget.clear_output(wait=True)
            print(f"🔗 正在連接 YouTube 並取得影片資訊: {youtube_url}")
            print(f"🎬 影片標題：{current_video_info['title']}")
            print(f"⏱️ 時長：{format_duration(current_video_info['duration_sec'])}")

        audio_stream = yt.streams.get_audio_only()
        if not audio_stream: audio_stream = yt.streams.filter(only_audio=True, file_extension='m4a').order_by('abr').desc().first()
        if not audio_stream: audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc().first()
        if not audio_stream: audio_stream = yt.streams.filter(only_audio=True, file_extension='webm').order_by('abr').desc().first()

        if not audio_stream:
            with status_output_widget: print("❌ 錯誤：找不到可用的純音訊流。"); return None

        original_mimetype = audio_stream.mime_type
        original_abr = audio_stream.abr
        original_filesize = audio_stream.filesize

        # --- 檔名控制強化 (移除 parse_filename 依賴) ---
        # 從 audio_stream.default_filename 或 audio_stream.subtype 推斷副檔名
        default_fn = audio_stream.default_filename
        file_ext = os.path.splitext(default_fn)[1].lower() # e.g. .mp4, .webm

        # 如果副檔名是 .mp4 但類型是 audio/mp4 或 audio/aac，則傾向使用 .m4a
        if file_ext == '.mp4' and ('audio/mp4' in original_mimetype or 'audio/aac' in original_mimetype):
            file_ext = '.m4a'
        elif not file_ext: # 如果 default_filename 沒有副檔名 (不太可能，但以防萬一)
            if 'webm' in original_mimetype: file_ext = '.webm'
            elif 'aac' in original_mimetype: file_ext = '.m4a'
            elif 'mp4' in original_mimetype: file_ext = '.m4a' # 假設 audio mp4 是 m4a
            else: file_ext = '.audio' # 未知副檔名

        final_filename_stem = f"{current_video_info['sanitized_title']}_audio"
        final_filename = f"{final_filename_stem}{file_ext}"

        with status_output_widget:
            status_output_widget.clear_output(wait=True)
            print(f"🔗 正在連接 YouTube 並取得影片資訊: {youtube_url}")
            print(f"🎬 影片標題：{current_video_info['title']}")
            print(f"⏱️ 時長：{format_duration(current_video_info['duration_sec'])}")
            print(f"🎧 找到原始音訊流：{original_mimetype}, 位元率約 {original_abr if original_abr else '未知'}")
            if original_filesize: print(f"💾 預計檔案大小：{format_bytes(original_filesize)}")
            print(f"⏳ 開始下載原始音訊，將儲存為: {final_filename}")

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        downloaded_audio_path = audio_stream.download(output_path=DOWNLOAD_DIR, filename=final_filename)
        actual_filename = os.path.basename(downloaded_audio_path)
        actual_filesize = os.path.getsize(downloaded_audio_path)

        with status_output_widget:
            status_output_widget.clear_output(wait=True)
            print(f"✅ 音訊下載完成！")
            print(f"   📄 檔案：{actual_filename}")
            print(f"   💾 大小：{format_bytes(actual_filesize)}")
            print(f"   📍 路徑：{downloaded_audio_path}")

        return {
            'audio_path': downloaded_audio_path, 'video_title': current_video_info['title'],
            'sanitized_title': current_video_info['sanitized_title'],
            'duration_sec': current_video_info['duration_sec'],
            'actual_filename': actual_filename, 'mime_type': original_mimetype
        }
    except RegexMatchError:
        with status_output_widget: status_output_widget.clear_output(wait=True); print("❌ 錯誤：YouTube 連結格式不正確。");
    except VideoUnavailable:
        with status_output_widget: status_output_widget.clear_output(wait=True); print("❌ 錯誤：該影片無法取得。");
    except OSError as e:
        with status_output_widget:
            status_output_widget.clear_output(wait=True)
            print(f"❌ 音訊下載時發生作業系統錯誤：{e}")
            if e.errno == 36: # Filename too long
                print("   錯誤原因：檔案名稱過長。已嘗試縮短，但可能標題包含過多特殊或多位元組字元。")
            import traceback
            traceback.print_exc(file=sys.stdout)
    except Exception as e:
        with status_output_widget:
            status_output_widget.clear_output(wait=True)
            print(f"❌ 音訊下載時發生未預期的錯誤：{e}")
            import traceback
            traceback.print_exc(file=sys.stdout)
    return None

# @title 5. Gemini API 互動函式
# ==============================================================================
# Part 5: Gemini API 互動
# ==============================================================================
def upload_audio_to_gemini_files_for_transcription(audio_path, original_filename_for_display, status_output_widget, audio_mime_type=None):
    with status_output_widget:
        print(f"☁️ 正在上傳音訊檔案 '{original_filename_for_display}' 至 Gemini Files API...")
    try:
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            with status_output_widget:
                print(f"🔴 錯誤：音訊檔案 '{audio_path}' 不存在或為空。")
            return None

        if not audio_mime_type: # 自動偵測 MIME 類型
            ext = os.path.splitext(audio_path)[1].lower()
            mime_map = {'.mp3': 'audio/mp3', '.m4a': 'audio/m4a', '.aac': 'audio/aac',
                        '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.flac': 'audio/flac',
                        '.webm': 'audio/webm', '.mp4': 'audio/mp4'} # mp4 can be audio container
            audio_mime_type = mime_map.get(ext, 'application/octet-stream') # Default if unknown
            # Gemini API 傾向於 'audio/aac' 而非 'audio/m4a' 或 'audio/mp4' (for audio only)
            if audio_mime_type == 'audio/m4a' or audio_mime_type == 'audio/mp4':
                 audio_mime_type = 'audio/aac' # As per Gemini documentation preferences

        display_name_for_upload = os.path.basename(original_filename_for_display)
        audio_file_resource = genai.upload_file(path=audio_path, display_name=display_name_for_upload, mime_type=audio_mime_type)

        with status_output_widget:
            print(f"✅ 音訊檔案 '{display_name_for_upload}' ({format_bytes(os.path.getsize(audio_path))}) 已成功上傳。")
            print(f"   Gemini File API 資源名稱: {audio_file_resource.name}")
        return audio_file_resource
    except Exception as e:
        with status_output_widget:
            print(f"🔴 上傳音訊檔案 '{original_filename_for_display}' 失敗: {e}")
            if hasattr(e, 'message') and 'Unsupported MIME type' in str(e.message) or \
               'mime type' in str(e).lower(): # Check if error message indicates MIME type issue
                print(f"   提示：偵測到的MIME類型為 '{audio_mime_type}'。請確認此格式是否受 Gemini API 支援，或影片的音訊編碼是否特殊。")
            import traceback
            traceback.print_exc(file=sys.stdout)
        return None

def get_summary_and_transcript_from_gemini(gemini_file_resource, model_api_name, video_title_for_prompt, original_audio_filename_for_log, status_output_widget):
    with status_output_widget:
        print(f"🤖 正在使用模型 '{model_api_name}' 處理音訊 '{original_audio_filename_for_log}' (來自影片: {video_title_for_prompt})，請求摘要與逐字稿...")

    prompt_text = f"""請您扮演一位專業的逐字稿分析師。
您將收到一個名為 '{original_audio_filename_for_log}' (原始影片標題為: '{video_title_for_prompt}') 的音訊檔案。請完成以下兩項任務，並嚴格依照指定格式（包含標記）輸出，所有文字內容請使用繁體中文（台灣用語習慣）：

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
        response = model.generate_content(
            [prompt_text, gemini_file_resource],
            request_options={'timeout': 3600} # 增加超時時間
        )
        full_response_text = response.text
        summary_text = "未擷取到重點摘要。"
        transcript_text = "未擷取到詳細逐字稿。"

        summary_match = re.search(r"\[重點摘要開始\](.*?)\[重點摘要結束\]", full_response_text, re.DOTALL)
        if summary_match: summary_text = summary_match.group(1).strip()

        transcript_match = re.search(r"\[詳細逐字稿開始\](.*?)\[詳細逐字稿結束\]", full_response_text, re.DOTALL)
        if transcript_match:
            transcript_text = transcript_match.group(1).strip()
        elif "---[逐字稿分隔線]---" in full_response_text: # 嘗試備用分割
            parts = full_response_text.split("---[逐字稿分隔線]---", 1)
            if len(parts) > 1:
                potential_transcript = parts[1].replace("[詳細逐字稿結束]", "").strip()
                # 如果摘要也沒匹配到，但分隔線前的部分有結束標記，也嘗試擷取
                if not summary_match and "[重點摘要結束]" in parts[0]:
                    summary_text = parts[0].split("[重點摘要結束]",1)[0].replace("[重點摘要開始]","").strip()

                if transcript_text == "未擷取到詳細逐字稿。" and potential_transcript : # 只有在主要方法失敗時才用備用
                    transcript_text = potential_transcript


        # 如果兩種都沒擷取到，且沒有分隔線，可能模型未按格式輸出
        if summary_text == "未擷取到重點摘要。" and transcript_text == "未擷取到詳細逐字稿。" and "---[逐字稿分隔線]---" not in full_response_text:
            transcript_text = full_response_text # 將全部回應視為逐字稿
            summary_text = "（自動摘要失敗，請參考下方逐字稿自行整理）"


        filename_base = sanitize_filename(video_title_for_prompt)
        txt_filename = f"{filename_base}_摘要與逐字稿.txt"
        txt_file_path = os.path.join(DOWNLOAD_DIR, txt_filename)
        with open(txt_file_path, "w", encoding="utf-8") as f:
            f.write(f"影片標題：{video_title_for_prompt}\n\n")
            f.write("="*30 + " 重點摘要 " + "="*30 + "\n")
            f.write(summary_text + "\n\n")
            f.write("="*30 + " 詳細逐字稿 " + "="*30 + "\n")
            f.write(transcript_text + "\n")

        with status_output_widget:
            print(f"✅ 摘要與逐字稿已生成並儲存至：{txt_file_path}")
        return {'summary_text': summary_text, 'transcript_text': transcript_text, 'txt_file_path': txt_file_path }
    except Exception as e:
        with status_output_widget:
            print(f"🔴 模型處理音訊時發生錯誤 (摘要與逐字稿): {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'): print(f"   API Feedback: {e.response.prompt_feedback}")
            import traceback
            traceback.print_exc(file=sys.stdout)
        return None

def generate_html_report_from_gemini(summary_text_for_html, transcript_text_for_html, model_api_name, video_title_for_html, status_output_widget):
    with status_output_widget:
        print(f"🎨 正在使用模型 '{model_api_name}' 將文字內容轉換為 HTML 報告 (來自影片: {video_title_for_html})...")

    html_generation_prompt_template = f"""請生成一個完整的HTML檔案，該檔案應包含響應式設計（Responsive Web Design）的考量，並將提供的內容整合成一個頁面。所有文字內容請使用繁體中文（台灣用語習慣）。頁面內容分為兩大部分：「重點摘要」和「逐字稿」。

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
    * 當字體大小按鈕被選中時，可以給予該按鈕一個視覺上的「活躍」狀態（例如改變背景色或邊框）。

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
    try:
        model = genai.GenerativeModel(model_api_name)
        # --- 這行是修正的地方 ---
        response = model.generate_content(html_generation_prompt_template, request_options={'timeout': 1800})
        # --- 修正結束 ---
        generated_html_content = response.text

        # 清理 Gemini 可能添加的 Markdown 標記 (```html ... ```)
        if generated_html_content.strip().startswith("```html"): generated_html_content = generated_html_content.strip()[7:]
        if generated_html_content.strip().endswith("```"): generated_html_content = generated_html_content.strip()[:-3]
        generated_html_content = generated_html_content.strip()

        # 確保是完整的 HTML 文件
        doctype_pos = generated_html_content.lower().find("<!doctype html>")
        if doctype_pos != -1:
            generated_html_content = generated_html_content[doctype_pos:]
        else: # 如果沒有 doctype，嘗試從 <html> 標籤開始
            html_tag_pos = generated_html_content.lower().find("<html")
            if html_tag_pos != -1:
                generated_html_content = generated_html_content[html_tag_pos:]
            else: # 如果連 <html> 都沒有，則警告
                with status_output_widget: print("⚠️ 警告：AI模型生成的HTML內容可能不完整或格式不符，未找到 `<!DOCTYPE html>` 或 `<html>` 起始標籤。")


        filename_base = sanitize_filename(video_title_for_html)
        html_filename = f"{filename_base}_AI生成報告.html"
        html_file_path = os.path.join(DOWNLOAD_DIR, html_filename)
        with open(html_file_path, "w", encoding="utf-8") as f: f.write(generated_html_content)

        with status_output_widget: print(f"✅ HTML 報告已生成並儲存至：{html_file_path}")
        return html_file_path
    except Exception as e:
        with status_output_widget:
            print(f"🔴 模型生成 HTML 時發生錯誤: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'): print(f"   API Feedback: {e.response.prompt_feedback}")
            import traceback
            traceback.print_exc(file=sys.stdout)
        return None

def clean_temp_gemini_files(gemini_files_to_delete, status_output_widget):
    if not gemini_files_to_delete: return
    with status_output_widget: print(f"🗑️ 正在清理已上傳的 Gemini API 檔案...")
    count = 0
    for gf_name in gemini_files_to_delete:
        try: genai.delete_file(gf_name); count += 1
        except Exception as e_del_gf:
            with status_output_widget: print(f"   🔴 從 Gemini API 刪除檔案 '{gf_name}' 失敗: {e_del_gf}")
    with status_output_widget: print(f"   👍 已成功清理 {count} 個 Gemini API 檔案。")

# @title 6. 使用者介面 (UI) 與主流程
# ==============================================================================
# Part 6: 使用者介面 (UI) 與主流程
# ==============================================================================
FONT_COLOR = "#FCFCFC"

ui_title_label = widgets.HTML(f"<h1 style='text-align: center; color: {FONT_COLOR};'>🎶 YouTube 影片 AI 智能助理</h1>")
ui_description_html = widgets.HTML(f"""
<p style="text-align: center; color: {FONT_COLOR}; margin-bottom: 20px;">
    只需貼上 YouTube 影片網址，選擇 AI 模型，即可獲得影片的重點摘要、詳細逐字稿以及精美的 HTML 報告！
</p><hr style='border-color: #444;'>
""")

youtube_url_input = widgets.Text(
    placeholder='範例: https://www.youtube.com/watch?v=your_video_id',
    description='影片網址:',
    layout=widgets.Layout(width='90%'),
    style={'description_width': 'initial'}
)

# 新增：只下載逐字稿選項
only_transcript_checkbox = widgets.Checkbox(
    value=False,
    description='只下載逐字稿 (TXT 格式，不生成 HTML 報告)',
    disabled=False,
    indent=False,
    layout=widgets.Layout(margin='10px 0 20px 0', width='auto'),
    style={'description_width': 'initial', 'text_color': FONT_COLOR}
)


process_button = widgets.Button(
    description="🚀 開始處理影片", button_style='primary', icon='cogs',
    layout=widgets.Layout(width='auto', margin='20px 0px 25px 0px')
)

status_output_area = widgets.Output(layout=widgets.Layout(width='95%', border='1px solid #444', padding='10px', margin='10px 0', max_height='350px', overflow_y='auto'))
results_title_html = widgets.HTML(f"<h4 style='color: {FONT_COLOR}; margin-top: 20px;'>📄 處理結果與檔案下載：</h4>")

# 使用VBox作為按鈕容器，以便動態添加和移除，但保持現有按鈕不消失
# 每個結果項目將是一個 HBox，包含預覽和下載按鈕
results_container = widgets.VBox([], layout=widgets.Layout(width='95%', margin='10px 0'))

# 修改預覽區塊的樣式，使其與 Colab 背景更一致
txt_preview_area = widgets.Output(layout=widgets.Layout(width='95%', margin='5px 0', max_height='250px', overflow_y='auto', border='1px dashed #666', padding='8px', background_color='transparent'))
html_preview_area = widgets.Output(layout=widgets.Layout(width='95%', margin='5px 0', max_height='450px', overflow_y='auto', border='1px dashed #007bff', padding='8px', background_color='transparent'))


def create_action_buttons(file_path, file_type, file_display_name_short, file_full_name):
    # file_display_name_short: "TXT 逐字稿" 或 "HTML 報告"
    # file_full_name: 實際檔案名稱，用於下載提示
    preview_button = widgets.Button(description=f"👁️ 預覽 {file_display_name_short}", button_style='info', layout=widgets.Layout(margin='0 8px 8px 0', width='auto'))
    download_button = widgets.Button(description=f"💾 下載 {file_display_name_short}", button_style='success', layout=widgets.Layout(margin='0 8px 8px 0', width='auto'))
    target_preview_area = txt_preview_area if file_type == 'txt' else html_preview_area if file_type == 'html' else None

    def on_preview_clicked(b):
        if target_preview_area:
            with target_preview_area:
                target_preview_area.clear_output(wait=True)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
                    if file_type == 'txt':
                        escaped_content = html.escape(content)
                        # 將背景色設定為透明，文字顏色設定為適合Colab深色背景的淺色
                        display(HTML(f"<p style='font-size:small; color: #AAA;'>--- {file_display_name_short} 內容預覽 ---</p><pre style='white-space: pre-wrap; word-wrap: break-word; background-color: transparent; color: #E0E0E0; padding: 10px; border-radius: 4px;'>{escaped_content}</pre>"))
                    elif file_type == 'html':
                        # HTML預覽，設定容器背景為透明，讓它與Colab背景一致
                        # HTML內容本身的淺色模式會是白底黑字，達到「白字背景透明」效果
                        display(HTML(f"<p style='font-size:small; color: #AAA;'>--- {file_display_name_short} 內容預覽 (Colab內嵌預覽可能與瀏覽器直接開啟略有差異) ---</p><div style='background-color: transparent; padding:10px; border-radius:5px;'>{content}</div>"))
                except Exception as e_preview: print(f"🔴 預覽檔案 '{file_full_name}' 失敗: {e_preview}")
        else: # 理論上 target_preview_area 不應為 None，除非 file_type 傳錯
            with status_output_area: print(f"ℹ️ 此檔案類型 ({file_type}) 無法在此處預覽。")

    def on_download_clicked(b):
        try:
            colab_files.download(file_path)
            with status_output_area: print(f"🚀 開始下載檔案: {file_full_name}")
        except Exception as e_download:
            with status_output_area: print(f"🔴 下載檔案 '{file_full_name}' 失敗: {e_download}")

    preview_button.on_click(on_preview_clicked)
    download_button.on_click(on_download_clicked)
    return widgets.HBox([preview_button, download_button])

def on_process_button_clicked(b):
    with status_output_area: status_output_area.clear_output()
    results_container.children = [] # 清空之前的結果按鈕
    with txt_preview_area: txt_preview_area.clear_output()
    with html_preview_area: html_preview_area.clear_output()
    current_video_info.update({'title': None, 'sanitized_title': None, 'duration_sec': None})

    yt_url = youtube_url_input.value.strip()
    selected_model_api = model_selector_dropdown.value
    should_only_download_transcript = only_transcript_checkbox.value

    if not API_KEY_CONFIGURED:
        with status_output_area: print("🔴 錯誤：Google API 金鑰未設定或無效。請檢查步驟2。"); return
    if not yt_url:
        with status_output_area: print("🔴 錯誤：請先輸入 YouTube 影片網址。"); return
    if not selected_model_api:
        with status_output_area: print("🔴 錯誤：請先選擇一個 AI 模型。"); return

    process_button.disabled = True; process_button.description = "⏳ 處理中，請稍候..."
    audio_info = None; gemini_audio_file_resource = None; local_audio_path_to_clean = None

    try:
        with status_output_area: status_output_area.clear_output(wait=True); print("--------------------------------------------------\n⚙️ 步驟 1/3 (或 1/4)：下載 YouTube 音訊...\n--------------------------------------------------")
        audio_info = download_youtube_audio(yt_url, status_output_area)
        if not audio_info or not audio_info.get('audio_path'): raise ValueError("音訊下載失敗或未返回有效路徑。")
        local_audio_path_to_clean = audio_info['audio_path']

        with status_output_area: print("\n--------------------------------------------------\n⚙️ 步驟 2/3 (或 2/4)：上傳音訊至 Gemini 雲端...\n--------------------------------------------------")
        gemini_audio_file_resource = upload_audio_to_gemini_files_for_transcription(audio_info['audio_path'], audio_info['actual_filename'], status_output_area, audio_info.get('mime_type'))
        if not gemini_audio_file_resource: raise ValueError("音訊上傳至 Gemini Files API 失敗。")

        with status_output_area: print("\n--------------------------------------------------\n⚙️ 步驟 3/3 (或 3/4)：AI 模型生成摘要與逐字稿...\n--------------------------------------------------")
        first_pass_result = get_summary_and_transcript_from_gemini(gemini_audio_file_resource, selected_model_api, audio_info['video_title'], audio_info['actual_filename'], status_output_area)
        if not first_pass_result or not first_pass_result.get('txt_file_path'): raise ValueError("AI 生成摘要與逐字稿失敗。")

        # 顯示TXT下載/預覽按鈕
        txt_buttons = create_action_buttons(first_pass_result['txt_file_path'], 'txt', 'TXT 逐字稿', os.path.basename(first_pass_result['txt_file_path']))
        results_container.children = list(results_container.children) + [txt_buttons]


        if not should_only_download_transcript: # 如果不只下載逐字稿，則生成HTML報告
            with status_output_area: print("\n--------------------------------------------------\n⚙️ 步驟 4/4：AI 模型美化並生成 HTML 報告...\n--------------------------------------------------")
            html_file_path = generate_html_report_from_gemini(first_pass_result['summary_text'], first_pass_result['transcript_text'], selected_model_api, audio_info['video_title'], status_output_area)
            if html_file_path:
                html_buttons = create_action_buttons(html_file_path, 'html', 'HTML 報告', os.path.basename(html_file_path))
                results_container.children = list(results_container.children) + [html_buttons]
        else:
            with status_output_area: print("\n⏩ 您已選擇只下載逐字稿，跳過 HTML 報告生成步驟。")

        with status_output_area: print("\n==================================================\n🎉🎉🎉 全部處理完成！請在下方查看結果和下載檔案。 🎉🎉🎉\n==================================================")
    except Exception as e_main:
        with status_output_area:
            print(f"\n❌ 主流程發生錯誤：{e_main}")
            print("   請檢查上述日誌獲取詳細錯誤資訊。")
            import traceback
            traceback.print_exc(file=sys.stdout)
    finally:
        if gemini_audio_file_resource and hasattr(gemini_audio_file_resource, 'name'):
            with status_output_area: print("\nℹ️ 正在清理雲端臨時音訊檔案...")
            clean_temp_gemini_files([gemini_audio_file_resource.name], status_output_area)
        if local_audio_path_to_clean and os.path.exists(local_audio_path_to_clean):
            try:
                os.remove(local_audio_path_to_clean)
                with status_output_area: print(f"   本地臨時音訊檔案 '{os.path.basename(local_audio_path_to_clean)}' 已清理。")
            except Exception as e_clean_local:
                with status_output_area: print(f"   🔴 清理本地臨時音訊檔案 '{os.path.basename(local_audio_path_to_clean)}' 失敗: {e_clean_local}")
        process_button.disabled = False; process_button.description = "🚀 開始處理影片"

process_button.on_click(on_process_button_clicked)

# @title 7. 啟動並顯示完整介面
# ==============================================================================
# Part 7: 啟動介面
# ==============================================================================
main_layout_vbox = widgets.VBox([
    ui_title_label,
    ui_description_html,
    widgets.HTML(f"<h3 style='color: {FONT_COLOR}; margin-top:15px;'>步驟 1: 輸入 YouTube 影片網址</h3>"),
    youtube_url_input,
    only_transcript_checkbox, # 新增的核取方塊
    widgets.HTML(f"<hr style='border-color: #444; margin: 20px 0;'><h3 style='color: {FONT_COLOR};'>步驟 2: 選擇要使用的 AI 模型</h3>"),
    widgets.HTML(f"<p style='font-size:small; color: #B0B0B0;'>下方列表已大致按 Pro > Flash > 其他，同系列中新版優先排序。</p>"),
    model_selector_dropdown,
    model_details_html,
    widgets.HTML(f"<hr style='border-color: #444; margin: 20px 0;'><h3 style='color: {FONT_COLOR};'>步驟 3: 開始處理</h3>"),
    process_button,
    widgets.HTML(f"<hr style='border-color: #444; margin: 25px 0 10px 0;'><h3 style='color: {FONT_COLOR};'>📊 操作日誌與狀態：</h3>"),
    status_output_area,
    results_title_html,
    results_container, # 將 results_display_area 改為 results_container
    widgets.HTML(f"<p style='font-size:small; color: #B0B0B0; margin-top:20px;'>--- TXT 檔案預覽區 ---</p>"),
    txt_preview_area,
    widgets.HTML(f"<p style='font-size:small; color: #B0B0B0; margin-top:15px;'>--- HTML 報告預覽區 ---</p>"),
    html_preview_area
], layout=widgets.Layout(padding='10px'))

if API_KEY_CONFIGURED:
    display(main_layout_vbox)
    populate_model_dropdown(status_output_area) # 確保在主介面顯示後再嘗試填充模型列表
else:
    display(HTML(f"<p style='color:#FF6B6B; font-weight:bold; font-size:large;'>🔴 API 金鑰未設定或設定失敗，無法啟動完整介面。請返回執行「2. API 金鑰與 Gemini 模型設定」區塊並檢查 Colab Secrets 中的 GOOGLE_API_KEY 設定。</p>"))
