#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import logging
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
import json
import asyncio
from typing import Dict, Any

import google.generativeai as genai

from db.client import DBClient, get_client
from tools import downloader, gemini_uploader, gemini_analyzer, report_storage
from src.api.sse_manager import get_sse_broadcaster
from src.api.html_templates import render_youtube_task_item, render_downloader_task_item

# --- 路徑設定 ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))
SRC_DIR = ROOT_DIR / "src"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
log = logging.getLogger('orchestrator')

# --- 全域變數 ---
processes = []
threads = []
stop_event = threading.Event()
db_client = None

# --- 公用函式 ---
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def stream_reader(stream, prefix, ready_event=None, ready_signal=None, port_list=None, port_regex=None):
    try:
        for line in iter(stream.readline, ''):
            if not line: break
            stripped_line = line.strip()
            log.info(f"[{prefix}] {stripped_line}")
            if ready_event and not ready_event.is_set() and ready_signal and ready_signal in stripped_line:
                ready_event.set()
            if port_list is not None and port_regex:
                match = re.search(port_regex, stripped_line)
                if match:
                    port = int(match.group(1))
                    port_list.append(port)
    except Exception as e:
        log.error(f"讀取流 '{prefix}' 時發生錯誤: {e}", exc_info=True)

# --- 總指揮核心邏輯 ---
def run_youtube_pipeline(
    task_id: str,
    loop: asyncio.AbstractEventLoop,
    uploads_dir: Path
):
    log.info(f"🧵 [執行緒] 開始處理 YouTube 任務鏈，起始 ID: {task_id}")
    db_client = get_client()
    dependent_task_id = None

    def broadcast(payload: Dict[str, Any], task_type: str):
        log.info(f"[SSE Broadcast] 準備廣播 HTML 片段，任務類型: {task_type}")
        task_info_for_render = db_client.get_task_status(payload.get("task_id"))
        payload_for_render = payload.copy()
        payload_for_render['task_info'] = task_info_for_render

        if 'download_only' in task_type:
            html_content = render_downloader_task_item(payload_for_render)
        else:
            html_content = render_youtube_task_item(payload_for_render)

        sse_broadcaster = get_sse_broadcaster()
        message = {
            "type": "YOUTUBE_TASK_UPDATE",
            "payload": {"task_id": payload.get("task_id"), "html": html_content}
        }
        asyncio.run_coroutine_threadsafe(sse_broadcaster.broadcast(message), loop)

    if os.environ.get("API_MODE") == "mock":
        log.warning("⚠️ Orchestrator 偵測到模擬模式，將執行模擬管線。")
        try:
            task_info = db_client.get_task_status(task_id)
            task_payload = json.loads(task_info.get('payload', '{}'))
            url = task_payload.get('url', 'mock_url')
            broadcast({"task_id": task_id, "status": "downloading", "message": f"正在下載 (模擬): {url.split('/')[-1]}"}, task_info['type'])
            time.sleep(2)
            video_title = f"模擬影片_{task_id[:8]}"
            mock_media_path = uploads_dir / f"{video_title}.mp3"
            mock_media_path.write_text("This is a mock audio file.")
            download_result = {"output_path": str(mock_media_path), "video_title": video_title}
            db_client.update_task_status(task_id, '已完成', json.dumps(download_result))
            dependent_task_id = db_client.find_dependent_task(task_id)
            if not dependent_task_id:
                broadcast({"task_id": task_id, "status": "completed", "result": download_result}, "youtube_download_only")
                return
            process_task_info = db_client.get_task_status(dependent_task_id)
            broadcast({"task_id": dependent_task_id, "status": "processing", "message": "正在處理 AI 分析 (模擬)..."}, "gemini_process")
            time.sleep(3)
            mock_report_path = uploads_dir / "reports" / f"{video_title}_report.html"
            mock_report_path.parent.mkdir(parents=True, exist_ok=True)
            mock_report_path.write_text(f"<html><body><h1>{video_title}</h1><p>這是一份由模擬模式產生的報告。</p></body></html>")
            final_result = {"output_path": str(mock_report_path), "video_title": video_title, "total_tokens_used": 100}
            db_client.update_task_status(dependent_task_id, '已完成', json.dumps(final_result))
            broadcast({"task_id": dependent_task_id, "status": "completed", "result": final_result}, "gemini_process")
        except Exception as e:
            log.error(f"❌ 模擬 YouTube 處理流程中發生錯誤: {e}", exc_info=True)
        return

    try:
        task_info = db_client.get_task_status(task_id)
        if not task_info: raise ValueError(f"找不到起始任務 {task_id}")
        task_payload = json.loads(task_info['payload'])
        url = task_payload['url']
        broadcast({"task_id": task_id, "status": "downloading", "message": f"正在下載: {url}"}, task_info['type'])
        download_result = downloader.download_media(youtube_url=url, output_dir=uploads_dir, download_type=task_payload.get("download_type", "audio"), custom_filename=task_payload.get("custom_filename"), cookies_file=str(uploads_dir / "cookies.txt"))
        media_path = Path(download_result["output_path"])
        video_title = download_result["video_title"]
        log.info(f"✅ 媒體下載完成: {media_path}")
        if task_info['type'] == 'youtube_download_only':
            db_client.update_task_status(task_id, '已完成', json.dumps(download_result))
            broadcast({"task_id": task_id, "status": "completed", "result": download_result}, "youtube_download_only")
            return
        db_client.update_task_status(task_id, '已完成', json.dumps(download_result))
        dependent_task_id = db_client.find_dependent_task(task_id)
        if not dependent_task_id: raise ValueError(f"找不到依賴於下載任務 {task_id} 的 gemini_process 任務")
        process_task_info = db_client.get_task_status(dependent_task_id)
        process_payload = json.loads(process_task_info['payload'])
        model_name, api_key = process_payload['model'], process_payload['api_key']
        os.environ["GOOGLE_API_KEY"] = api_key
        broadcast({"task_id": dependent_task_id, "status": "uploading", "message": "正在上傳音訊至 Gemini..."}, "gemini_process")
        gemini_file = gemini_uploader.upload_file(media_path)
        try:
            broadcast({"task_id": dependent_task_id, "status": "processing", "message": f"使用 {model_name} 進行 AI 分析..."}, "gemini_process")
            model = genai.GenerativeModel(model_name)
            summary, transcript, tokens_used_analisys = gemini_analyzer.get_summary_and_transcript(model=model, gemini_file_resource=gemini_file, video_title=video_title, original_filename=media_path.name)
            html_content, tokens_used_html = gemini_analyzer.generate_html_report(model=model, summary=summary, transcript=transcript, video_title=video_title)
            report_content = {"summary": summary, "transcript": transcript, "html_content": html_content}
            report_path = report_storage.save_report(content=report_content, video_title=video_title, output_dir=uploads_dir / "reports", output_format=process_payload.get("output_format", "html"))
            final_result = {"output_path": str(report_path), "video_title": video_title, "total_tokens_used": tokens_used_analisys + tokens_used_html}
            db_client.update_task_status(dependent_task_id, '已完成', json.dumps(final_result))
            log.info("✅ Gemini AI 處理完成。")
            broadcast({"task_id": dependent_task_id, "status": "completed", "result": final_result}, "gemini_process")
        finally:
            log.info(f"🗑️ 正在清理 Gemini 檔案: {gemini_file.name}")
            try:
                genai.delete_file(gemini_file.name)
                log.info("✅ Gemini 檔案清理成功。")
            except Exception as e:
                log.error(f"🔴 清理 Gemini 檔案 '{gemini_file.name}' 時失敗: {e}", exc_info=True)
    except Exception as e:
        log.error(f"❌ YouTube 處理流程中發生錯誤: {e}", exc_info=True)
        failed_task_id = dependent_task_id if dependent_task_id else task_id
        error_payload = {"error": str(e)}
        db_client.update_task_status(failed_task_id, 'failed', json.dumps(error_payload))
        broadcast({"task_id": failed_task_id, "status": "failed", **error_payload}, "unknown")

def main():
    parser = argparse.ArgumentParser(description="系統協調器。")
    parser.add_argument("--mock", action="store_true", help="如果設置，則 worker 將以模擬模式運行。")
    parser.add_argument("--port", type=int, default=None, help="指定 API 伺服器運行的固定埠號。")
    args, _ = parser.parse_known_args()
    global db_client
    try:
        log.info("--- [協調器啟動] ---")
        log.info("🔧 正在啟動資料庫管理者...")
        db_manager_port_list = []
        db_manager_cmd = [sys.executable, "src/db/manager.py"]
        db_manager_proc = subprocess.Popen(db_manager_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        processes.append(db_manager_proc)
        db_stdout_thread = threading.Thread(target=stream_reader, args=(db_manager_proc.stdout, 'db_manager'), kwargs={'port_list': db_manager_port_list, 'port_regex': r"DB_MANAGER_PORT: (\d+)"})
        db_stdout_thread.daemon = True
        threads.append(db_stdout_thread)
        db_stdout_thread.start()
        start_time = time.time()
        while not db_manager_port_list:
            if time.time() - start_time > 30: raise RuntimeError("等待資料庫管理者埠號超時。")
            if db_manager_proc.poll() is not None: raise RuntimeError(f"資料庫管理者程序在啟動期間意外終止，返回碼: {db_manager_proc.returncode}")
            time.sleep(0.1)
        db_manager_port = db_manager_port_list[0]
        os.environ['DB_MANAGER_PORT'] = str(db_manager_port)
        log.info(f"✅ 資料庫管理者已就緒，監聽於埠號: {db_manager_port}")
        db_client = get_client()
        log.info("✅ DB 客戶端初始化完成。")
        log.info("🔧 正在啟動 API 伺服器...")
        api_port = args.port if args.port else find_free_port()
        api_server_cmd = [sys.executable, "src/api/api_server.py", "--port", str(api_port)]
        if args.mock: api_server_cmd.append("--mock")
        api_env = os.environ.copy()
        if args.mock: api_env["API_MODE"] = "mock"
        proxy_url = f"http://127.0.0.1:{api_port}"
        api_proc = subprocess.Popen(api_server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', env=api_env)
        processes.append(api_proc)
        log.info(f"API 伺服器程序已啟動，PID: {api_proc.pid}，埠號: {api_port}")
        print(f"PROXY_URL: {proxy_url}", flush=True)
        api_stdout_thread = threading.Thread(target=stream_reader, args=(api_proc.stdout, 'api_server', None, None))
        api_stderr_thread = threading.Thread(target=stream_reader, args=(api_proc.stderr, 'api_server_stderr', None, None))
        threads.extend([api_stdout_thread, api_stderr_thread])
        for t in [api_stdout_thread, api_stderr_thread]:
            t.daemon = True
            t.start()
        log.info("--- [協調器進入監控模式] ---")
        while not stop_event.is_set():
            for proc in processes:
                if proc.poll() is not None: raise RuntimeError(f"子程序 {proc.args} (PID: {proc.pid}) 已意外終止，返回碼: {proc.returncode}")
            time.sleep(2)
    except (Exception, KeyboardInterrupt) as e:
        if isinstance(e, KeyboardInterrupt): log.warning("捕獲到手動中斷信號 (KeyboardInterrupt)...")
        else: log.critical(f"協調器發生致命錯誤: {e}", exc_info=True)
    finally:
        log.info("--- [協調器開始關閉程序] ---")
        stop_event.set()
        for p in reversed(processes):
            try:
                if p.poll() is None:
                    log.info(f"正在終止程序: {p.args} (PID: {p.pid})")
                    p.terminate()
                    p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning(f"程序 {p.pid} 未能在5秒內終止，將強制終止。")
                p.kill()
            except Exception as kill_e:
                log.error(f"終止程序 {p.pid} 時發生錯誤: {kill_e}")
        log.info("等待所有日誌執行緒結束...")
        for t in threads:
            if t.is_alive(): t.join(timeout=2)
        log.info("✅ 所有子程序與執行緒已清理完畢。協調器已關閉。")
        sys.exit(1 if 'e' in locals() and not isinstance(e, KeyboardInterrupt) else 0)

if __name__ == "__main__":
    main()
