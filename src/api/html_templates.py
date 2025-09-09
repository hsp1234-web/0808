# src/api/html_templates.py
"""
一個專門用於產生 HTML 片段的模組，以支援後端驅動的 UI 更新。
"""
from typing import Dict, Any
from pathlib import Path
import json
import html

def render_youtube_task_item(payload: Dict[str, Any]) -> str:
    """
    根據 YouTube 任務的 payload，渲染單個任務項目的 HTML。
    """
    task_id = payload.get("task_id", "")
    status = payload.get("status", "unknown")
    message = payload.get("message", status)
    result = payload.get("result", {})

    video_title = result.get("video_title") or payload.get("filename") or task_id
    video_title_escaped = html.escape(str(video_title))
    message_escaped = html.escape(str(message))

    status_class = ""
    lower_message = (message or '').lower()
    if 'downloading' in lower_message or '下載中' in lower_message:
        status_class = "status-downloading"
    elif 'processing' in lower_message or '分析中' in lower_message or 'uploading' in lower_message:
        status_class = "status-processing"

    status_content = ""
    if status == "completed":
        output_path = result.get("output_path", "#")
        file_type = 'text/html' if '.html' in output_path else 'text/plain'
        status_content = f"""
            <a href="#" class="btn-preview" data-testid="view-report-button"
               data-url="{html.escape(output_path)}"
               data-title="{video_title_escaped}"
               data-type="{file_type}"
               data-task-id="{task_id}">預覽</a>
        """
    else:
        status_content = f'<span class="task-status {status_class}">{message_escaped}</span>'

    return f"""
<div class="task-item" data-task-id="{task_id}">
  <span class="task-filename">{video_title_escaped}</span>
  <div class="task-actions">{status_content}</div>
</div>
""".strip()


def render_downloader_task_item(payload: Dict[str, Any]) -> str:
    """
    為僅下載的任務項目渲染 HTML。
    """
    task_id = payload.get("task_id", "")
    status = payload.get("status", "unknown")
    message = payload.get("message", status)
    result = payload.get("result", {})
    task_info = payload.get("task_info", {})

    task_payload = json.loads(task_info.get('payload', '{}')) if task_info else {}

    download_type_str = task_payload.get("download_type", "")
    if not download_type_str and result and 'output_path' in result:
        is_video = str(result['output_path']).endswith('.mp4')
        download_type_str = "video" if is_video else "audio"

    download_type_text = "影片" if "video" in download_type_str else "音訊"

    video_title = result.get("video_title") or task_payload.get("url", task_id)
    video_title_escaped = html.escape(str(video_title))
    message_escaped = html.escape(str(message))

    actions_html = ""
    if status == "completed" and result:
        output_path = result.get("output_path", "#")
        file_ext = Path(output_path).suffix
        file_type = 'video/mp4' if file_ext == '.mp4' else 'audio/mpeg'

        actions_html = f"""
            <a href="#" class="btn-preview" data-url="{html.escape(str(output_path))}" data-title="{video_title_escaped}" data-type="{file_type}" data-task-id="{task_id}">預覽</a>
            <a href="/api/download/{task_id}" class="btn-download" download="{video_title_escaped}{file_ext}">下載</a>
        """
    else:
        status_class = "status-downloading" if "downloading" in message.lower() else ""
        actions_html = f'<span class="task-status {status_class}">{message_escaped}</span>'

    return f"""
<div class="task-item" data-task-id="{task_id}">
  <span class="task-filename" title="{video_title_escaped}">{video_title_escaped} (僅下載{download_type_text})</span>
  <div class="task-actions">{actions_html}</div>
</div>
""".strip()
