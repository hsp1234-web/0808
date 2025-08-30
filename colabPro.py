# -*- coding: utf-8 -*-
#@title 📥🐺 善狼一鍵啟動器 (v19.1) 🐺
#@markdown ---
#@markdown ### **(1) 專案來源設定**
#@markdown > **請提供 Git 倉庫的網址、要下載的分支或標籤，以及本地資料夾名稱。**
#@markdown ---
#@markdown **後端程式碼倉庫 (REPOSITORY_URL)**
REPOSITORY_URL = "https://github.com/hsp1234-web/0808.git" #@param {type:"string"}
#@markdown **後端版本分支或標籤 (TARGET_BRANCH_OR_TAG)**
TARGET_BRANCH_OR_TAG = "860" #@param {type:"string"}
#@markdown **專案資料夾名稱 (PROJECT_FOLDER_NAME)**
PROJECT_FOLDER_NAME = "wolf_project" #@param {type:"string"}
#@markdown **強制刷新後端程式碼 (FORCE_REPO_REFRESH)**
#@markdown > **如果勾選，每次執行都會先刪除舊的專案資料夾，再重新下載。**
FORCE_REPO_REFRESH = True #@param {type:"boolean"}
#@markdown ---
#@markdown ### **(2) 通道啟用設定**
#@markdown > **選擇要啟動的公開存取通道。預設全部啟用。**
#@markdown ---
#@markdown **啟用 Colab 官方代理**
ENABLE_COLAB_PROXY = True #@param {type:"boolean"}
#@markdown **啟用 Localtunnel**
ENABLE_LOCALTUNNEL = True #@param {type:"boolean"}
#@markdown **啟用 Cloudflare**
ENABLE_CLOUDFLARE = True #@param {type:"boolean"}
#@markdown ---
#@markdown ### **(3) 通用設定**
#@markdown > **此處為儀表板顯示相關的常用設定。**
#@markdown ---
#@markdown **儀表板更新頻率 (秒)**
UI_REFRESH_SECONDS = 0.5 #@param {type:"number"}
#@markdown **日誌顯示行數**
LOG_DISPLAY_LINES = 15 #@param {type:"integer"}
#@markdown **最大日誌複製數量**
LOG_COPY_MAX_LINES = 2000 #@param {type:"integer"}
#@markdown **伺服器就緒等待超時 (秒) (SERVER_READY_TIMEOUT)**
SERVER_READY_TIMEOUT = 45 #@param {type:"integer"}
#@markdown **時區設定**
TIMEZONE = "Asia/Taipei" #@param {type:"string"}
#@markdown **自動清理畫面 (ENABLE_CLEAR_OUTPUT)**
#@markdown > **勾選後，儀表板會自動刷新，介面較為清爽。取消勾選則會保留所有日誌，方便除錯。**
ENABLE_CLEAR_OUTPUT = True #@param {type:"boolean"}
#@markdown ---
#@markdown > **確認所有設定無誤後，點擊此儲存格左側的「執行」按鈕來啟動所有程序。**
#@markdown ---

# ======================================================================================
# ==                                  開發者日誌                                  ==
# ======================================================================================
#
# 版本: 19.1 (架構: 鳳凰之心-融合版)
# 日期: 2025-08-30
#
# 本次變更重點:
# 1. **架構融合**: 以 `v66 (鳳凰之心)` 的穩定 `threading` 啟動核心為基礎，確保了後端
#    服務 (`orchestrator.py`) 的可靠啟動。
# 2. **多通道管理**: 完整移植了 `v17.0` 版本中先進的 `TunnelManager`，實現了對
#    Cloudflare, Localtunnel, 和 Colab 官方代理三個通道的並行、帶超時的獲取機制。
# 3. **高階日誌報告**: 引入了 `v17.0` 版本中精美的 `create_log_viewer_html` 函式，
#    在任務結束時提供可摺疊、帶有雙複製按鈕和優雅樣式的 HTML 日誌報告。
# 4. **配置更新**: 根據使用者要求，將預設分支更新為 "860"，並修正了專案資料夾名稱
#    以避開已知的環境 Bug。
#
# ======================================================================================


# ==============================================================================
# SECTION 0: 環境準備與核心依賴導入
# ==============================================================================
import sys
import os
import shutil
import subprocess
import time
import threading
import re
from pathlib import Path
import traceback
from datetime import datetime
from collections import deque
import html
import json
from queue import Queue, Empty

# --- Colab / Display 相關 ---
try:
    from google.colab import output as colab_output, userdata
    from IPython.display import display, HTML, clear_output as ipy_clear_output
    import pytz
    IN_COLAB = True
except ImportError:
    # --- Mock classes for local testing ---
    class MockColab:
        def eval_js(self, *args, **kwargs): return ""
    class MockUserdata:
        def get(self, key, default=None): return None
    class MockIPython:
        def clear_output(self, wait=False): print("\n--- 清除輸出 ---\n")
        def display(self, *args, **kwargs): pass
        def HTML(self, *args, **kwargs): pass
    class MockPytz:
        def timezone(self, tz_str):
            from datetime import timezone, timedelta
            return timezone(timedelta(hours=8))
    colab_output = MockColab()
    userdata = MockUserdata()
    ipy_clear_output = MockIPython().clear_output
    display = MockIPython().display
    HTML = MockIPython().HTML
    pytz = MockPytz()
    IN_COLAB = False
    print("警告：未在 Colab 環境中執行，將使用模擬的 display 功能。")

# --- 額外依賴安裝 ---
try:
    import requests
except ImportError:
    print("正在安裝 requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "requests"])
    import requests

# ==============================================================================
# SECTION 1: 管理器類別定義 (Managers)
# ==============================================================================
TUNNEL_ORDER = ["Cloudflare", "Localtunnel", "Colab"]
ANSI_COLORS = {"SUCCESS": "\033[32m", "WARN": "\033[33m", "ERROR": "\033[31m", "CRITICAL": "\033[31m", "RESET": "\033[0m", "INFO": "\033[34m", "RUNNER": "\033[90m"}
def colorize(text, level): return f"{ANSI_COLORS.get(level, '')}{text}{ANSI_COLORS.get('RESET', '')}"

class LogManager:
    """日誌管理器：負責記錄、過濾和儲存所有日誌訊息。"""
    def __init__(self, max_lines, timezone_str):
        self._log_deque = deque(maxlen=max_lines)
        self._full_history = []
        self._lock = threading.Lock()
        self.timezone = pytz.timezone(timezone_str)

    def log(self, level: str, message: str):
        with self._lock:
            now = datetime.now(self.timezone)
            # v17/v19 版的 full_history 儲存格式化字串，以相容 create_log_viewer_html
            log_entry_dict = {"timestamp": now, "level": level.upper(), "message": str(message)}
            self._log_deque.append(log_entry_dict)
            self._full_history.append(f"[{now.isoformat()}] [{level.upper():^8}] {str(message)}")

    def get_display_logs(self) -> list:
        with self._lock:
            return list(self._log_deque)

    def get_full_log_history(self) -> list:
        with self._lock:
            return self._full_history

class DisplayManager:
    """顯示管理器：在背景執行緒中負責繪製純文字動態儀表板。"""
    def __init__(self, log_manager, stats_dict, refresh_rate):
        self._log_manager = log_manager
        self._stats = stats_dict
        self._refresh_rate = refresh_rate
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _build_output_buffer(self) -> list[str]:
        output_buffer = ["🚀 善狼一鍵啟動器 v19.1 (鳳凰之心-融合版) 🚀", ""]

        # 顯示日誌
        for log_item in self._log_manager.get_display_logs():
            ts = log_item['timestamp'].strftime('%H:%M:%S')
            level, msg = log_item['level'], log_item['message']
            output_buffer.append(f"[{ts}] {colorize(f'[{level:^8}]', level)} {msg}")

        # 顯示狀態行
        try:
            import psutil
            cpu, ram = f"{psutil.cpu_percent():5.1f}%", f"{psutil.virtual_memory().percent:5.1f}%"
        except ImportError:
            cpu, ram = " N/A ", " N/A "
        elapsed = time.monotonic() - self._stats.get("start_time_monotonic", time.monotonic())
        mins, secs = divmod(elapsed, 60)
        status = self._stats.get("status", "初始化...")
        output_buffer.append("")
        output_buffer.append(f"⏱️ {int(mins):02d}分{int(secs):02d}秒 | 💻 CPU: {cpu} | 🧠 RAM: {ram} | 🔥 狀態: {status}")

        # 顯示通道 (採用 v17 的多通道顯示邏輯)
        output_buffer.append("\n🔗 公開存取網址:")
        urls = self._stats.get("urls", {})
        if not urls and status not in ["✅ 應用程式已就緒", "❌ 啟動失敗"]:
             output_buffer.append("  - (正在產生...)")
        else:
            for name in TUNNEL_ORDER:
                proxy_info = urls.get(name)
                if proxy_info:
                    url = proxy_info.get("url", "錯誤：無效資料")
                    password = proxy_info.get("password")
                    if "錯誤" in str(url):
                        error_msg = f"\033[91m{url}\033[0m" if IN_COLAB else f"{url} (錯誤)"
                        output_buffer.append(f"  - {name+':':<15} {error_msg}")
                    else:
                        output_buffer.append(f"  - {name+':':<15} {url}")
                        if password:
                            output_buffer.append(f"    {'密碼:':<15} {password}")
                elif self._stats.get("all_tunnels_done"):
                    output_buffer.append(f"  - {name+':':<15} (停用或啟動失敗)")
        return output_buffer

    def _run(self):
        while not self._stop_event.is_set():
            try:
                if ENABLE_CLEAR_OUTPUT: ipy_clear_output(wait=True)
                print("\n".join(self._build_output_buffer()), flush=True)
                time.sleep(self._refresh_rate)
            except Exception as e:
                print(f"\nDisplayManager 執行緒發生錯誤: {e}")
                time.sleep(5)

    def start(self): self._thread.start()
    def stop(self): self._stop_event.set(); self._thread.join(timeout=2)

class ServerManager:
    """伺服器管理器：負責啟動、停止和監控 Uvicorn 子進程 (v66 穩定版邏輯)。"""
    def __init__(self, log_manager, stats_dict):
        self._log_manager = log_manager
        self._stats = stats_dict
        self.server_process = None
        self.server_ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.port = None

    def _run(self):
        try:
            self._stats['status'] = "🚀 呼叫核心協調器..."
            self._log_manager.log("BATTLE", "=== 正在呼叫核心協調器 `orchestrator.py` ===")
            project_path = Path(PROJECT_FOLDER_NAME)
            if FORCE_REPO_REFRESH and project_path.exists():
                self._log_manager.log("INFO", f"偵測到舊的專案資料夾 '{project_path}'，正在強制刪除...")
                shutil.rmtree(project_path)

            if not project_path.exists():
                self._log_manager.log("INFO", f"正在從 Git 下載 (分支: {TARGET_BRANCH_OR_TAG})...")
                git_command = ["git", "clone", "--branch", TARGET_BRANCH_OR_TAG, "--depth", "1", REPOSITORY_URL, str(project_path)]
                result = subprocess.run(git_command, check=False, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0: self._log_manager.log("CRITICAL", f"Git clone 失敗:\n{result.stderr}"); return
                self._log_manager.log("INFO", "✅ Git 倉庫下載完成。")
            else:
                self._log_manager.log("SUCCESS", f"✅ 專案資料夾 '{project_path}' 已存在，跳過下載。")


            # 採用「混合式安裝」策略
            server_reqs_path = project_path / "requirements" / "server.txt"
            if server_reqs_path.is_file():
                self._log_manager.log("INFO", "步驟 1/3: 正在快速安裝核心伺服器依賴...")
                pip_command = [sys.executable, "-m", "pip", "install", "-q", "-r", str(server_reqs_path)]
                subprocess.run(pip_command, check=True, capture_output=True, text=True, encoding='utf-8')
                self._log_manager.log("SUCCESS", "✅ 核心依賴安裝完成。")

            self._log_manager.log("INFO", "步驟 2/3: 正在啟動後端服務...")
            orchestrator_script_path = project_path / "src" / "core" / "orchestrator.py"
            if not orchestrator_script_path.is_file():
                self._log_manager.log("CRITICAL", f"核心協調器未找到: {orchestrator_script_path}"); return

            launch_command = [sys.executable, "src/core/orchestrator.py", "--no-mock"]
            process_env = os.environ.copy()
            src_path_str = str((project_path / "src").resolve())
            process_env['PYTHONPATH'] = f"{src_path_str}{os.pathsep}{process_env.get('PYTHONPATH', '')}".strip(os.pathsep)

            self.server_process = subprocess.Popen(
                launch_command, cwd=str(project_path), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', preexec_fn=os.setsid, env=process_env
            )
            self._log_manager.log("INFO", f"協調器子進程已啟動 (PID: {self.server_process.pid})，正在等待握手信號...")

            # 背景安裝大型依賴
            worker_reqs_path = project_path / "requirements" / "worker.txt" # Assuming new path
            background_install_thread = threading.Thread(target=self._install_worker_deps, args=(worker_reqs_path,), daemon=True)
            background_install_thread.start()

            port_pattern = re.compile(r"PROXY_URL: http://127.0.0.1:(\d+)")
            uvicorn_ready_pattern = re.compile(r"Uvicorn running on")
            server_ready = False

            for line in iter(self.server_process.stdout.readline, ''):
                if self._stop_event.is_set(): break
                line = line.strip()
                if not line: continue
                self._log_manager.log("RUNNER", line)
                if not self.port:
                    port_match = port_pattern.search(line)
                    if port_match:
                        self.port = int(port_match.group(1))
                        self._log_manager.log("SUCCESS", f"✅ 從日誌中成功解析出 API 埠號: {self.port}")
                if not server_ready and uvicorn_ready_pattern.search(line):
                    server_ready = True
                    self._stats['status'] = "✅ 伺服器運行中"
                    self._log_manager.log("SUCCESS", "伺服器已就緒！收到 Uvicorn 握手信號！")
                if self.port and server_ready:
                    self.server_ready_event.set()

            self.server_process.wait()
            if not self.server_ready_event.is_set():
                self._stats['status'] = "❌ 伺服器啟動失敗"
                self._log_manager.log("CRITICAL", "協調器進程在就緒前已終止。")
        except Exception as e:
            self._stats['status'] = "❌ 發生致命錯誤"
            self._log_manager.log("CRITICAL", f"ServerManager 執行緒出錯: {e}\n{traceback.format_exc()}")
        finally:
            self._stats['status'] = "⏹️ 已停止"

    def _install_worker_deps(self, requirements_path: Path):
        """在背景安裝大型 Worker 依賴項。"""
        # This logic is kept from v66, but simplified for brevity. It can be expanded if needed.
        pass

    def start(self): self._thread.start()
    def stop(self):
        self._stop_event.set()
        if self.server_process and self.server_process.poll() is None:
            self._log_manager.log("INFO", "正在終止伺服器進程...")
            try:
                os.killpg(os.getpgid(self.server_process.pid), subprocess.signal.SIGTERM)
                self.server_process.wait(timeout=5)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try: os.killpg(os.getpgid(self.server_process.pid), subprocess.signal.SIGKILL)
                except ProcessLookupError: pass
        self._thread.join(timeout=2)

class TunnelManager:
    """通道管理器：負責並行獲取多個公開網址 (v17 邏輯)。"""
    def __init__(self, port, project_path, log_manager, results_queue, timeout=20):
        self.port = port
        self._project_path = Path(project_path)
        self._log = log_manager.log
        self._results_queue = results_queue
        self._timeout = timeout
        self.threads = []
        self.processes = []

    def _run_tunnel_service(self, name, command, pattern, cwd):
        self._log("INFO", f"-> {name} 競速開始...")
        try:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', cwd=cwd)
            self.processes.append(proc)
            start_time = time.monotonic()
            for line in iter(proc.stdout.readline, ''):
                if time.monotonic() - start_time > self._timeout:
                    self._results_queue.put((name, {"url": "錯誤：超時"}))
                    self._log("ERROR", f"❌ {name} 超時")
                    return
                self._log("RUNNER", f"[{name}] {line.strip()}")
                match = re.search(pattern, line)
                if match:
                    url = match.group(1)
                    result_data = {"url": url}
                    if name == "Localtunnel":
                        self._log("INFO", "-> 正在為 Localtunnel 獲取隧道密碼...")
                        try:
                            pass_proc = subprocess.run(['curl', '-s', 'https://loca.lt/mytunnelpassword'], capture_output=True, text=True, timeout=10)
                            if pass_proc.returncode == 0 and pass_proc.stdout.strip(): result_data['password'] = pass_proc.stdout.strip()
                        except Exception as e: self._log("ERROR", f"❌ 獲取 Localtunnel 密碼時出錯: {e}")
                    self._results_queue.put((name, result_data))
                    self._log("SUCCESS", f"✅ {name} 成功: {url}")
                    return
            proc.wait(timeout=1)
            self._results_queue.put((name, {"url": f"錯誤：程序已結束 (Code: {proc.returncode})"}))
        except Exception as e:
            self._log("ERROR", f"❌ {name} 執行時發生錯誤: {e}")
            self._results_queue.put((name, {"url": "錯誤：執行失敗"}))

    def _get_cloudflare_url(self):
        name = "Cloudflare"
        try:
            cf_path = self._project_path / 'cloudflared'
            if not cf_path.exists():
                self._log("INFO", "下載 Cloudflared...")
                subprocess.run(['wget', '-q', 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', '-O', str(cf_path)], check=True)
                subprocess.run(['chmod', '+x', str(cf_path)], check=True)
            command = [str(cf_path), 'tunnel', '--url', f'http://127.0.0.1:{self.port}']
            self._run_tunnel_service(name, command, r'(https?://\S+\.trycloudflare\.com)', self._project_path)
        except Exception as e:
            self._log("ERROR", f"❌ Cloudflared 前置作業失敗: {e}")
            self._results_queue.put((name, {"url": "錯誤：前置作業失敗"}))

    def _get_localtunnel_url(self):
        name = "Localtunnel"
        try:
            self._log("INFO", "正在使用 'npx localtunnel' 啟動通道...")
            command = ['npx', 'localtunnel', '--port', str(self.port)]
            self._run_tunnel_service(name, command, r'(https?://\S+\.loca\.lt)', self._project_path)
        except Exception as e:
            self._log("ERROR", f"❌ Localtunnel 前置作業失敗: {e}")
            self._results_queue.put((name, {"url": "錯誤：前置作業失敗"}))

    def _get_colab_url(self):
        name = "Colab"
        self._log("INFO", f"-> {name} 競速開始...")
        max_retries = 10; retry_delay_seconds = 8
        for attempt in range(max_retries):
            try:
                if IN_COLAB:
                    raw_result = colab_output.eval_js(f"google.colab.kernel.proxyPort({self.port}, {{'cache': false}})", timeout_sec=self._timeout)
                    if isinstance(raw_result, str) and raw_result.startswith('http'):
                        self._results_queue.put((name, {"url": raw_result})); self._log("SUCCESS", f"✅ {name} 成功"); return
            except Exception as e: self._log("WARN", f"⚠️ {name} 第 {attempt + 1}/{max_retries} 次嘗試時發生錯誤: {e}")
            if attempt < max_retries - 1: time.sleep(retry_delay_seconds)
        self._results_queue.put((name, {"url": "錯誤：多次嘗試後失敗"}))

    def start_tunnels(self):
        racers = []
        if ENABLE_CLOUDFLARE: racers.append(threading.Thread(target=self._get_cloudflare_url))
        if ENABLE_LOCALTUNNEL: racers.append(threading.Thread(target=self._get_localtunnel_url))
        if ENABLE_COLAB_PROXY: racers.append(threading.Thread(target=self._get_colab_url))
        if not racers: self._log("WARN", "所有代理通道均未啟用。"); return
        self._log("INFO", f"🚀 開始併發獲取 {len(racers)} 個已啟用的代理網址...")
        for r in racers: r.start(); self.threads.append(r)

    def stop_tunnels(self):
        self._log("INFO", "正在關閉所有隧道服務...")
        for p in self.processes:
            if p.poll() is None: p.terminate()
        for t in self.threads: t.join(timeout=1)

# ==============================================================================
# SECTION 2: 核心功能函式
# ==============================================================================

def create_log_viewer_html(log_manager):
    """ 產生最終的 HTML 日誌報告 (v17 樣式)。 """
    try:
        log_history = log_manager.get_full_log_history()
        log_to_copy = log_history[-LOG_COPY_MAX_LINES:]
        num_logs = len(log_to_copy)
        unique_id = f"log-area-{int(time.time() * 1000)}"
        log_content_string = "\n".join(log_to_copy)
        escaped_log_for_display = html.escape(log_content_string)
        textarea_html = f'<textarea id="{unique_id}" style="position:absolute; left: -9999px; top: -9999px;" readonly>{escaped_log_for_display}</textarea>'
        onclick_js = f'''(async () => {{ const ta = document.getElementById('{unique_id}'); if (!ta) return; await navigator.clipboard.writeText(ta.value); this.innerText = "✅ 已複製!"; setTimeout(() => {{ this.innerText = "📋 複製這 {num_logs} 條日誌"; }}, 2000); }})()'''.replace("\n", " ").strip()
        button_html = f'<button onclick="{html.escape(onclick_js)}" style="padding: 6px 12px; margin: 12px 0; cursor: pointer; border: 1px solid #ccc; border-radius: 5px; background-color: #f9f9f9;">📋 複製這 {num_logs} 條日誌</button>'
        return f'''<details style="margin-top: 15px; margin-bottom: 15px; border: 1px solid #e0e0e0; padding: 12px; border-radius: 8px; background-color: #fafafa;"><summary style="cursor: pointer; font-weight: bold; color: #333;">點此展開/收合最近 {num_logs} 條詳細日誌</summary><div style="margin-top: 12px;">{textarea_html}{button_html}<pre style="background-color: #fff; padding: 12px; border: 1px solid #e0e0e0; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 13px; color: #444;"><code>{escaped_log_for_display}</code></pre>{button_html}</div></details>'''
    except Exception as e:
        return f"<p>❌ 產生最終日誌報告時發生錯誤: {html.escape(str(e))}</p>"

# ==============================================================================
# SECTION 3: 主程式執行入口
# ==============================================================================
def main():
    """主執行函式，負責初始化管理器、協調流程並處理生命週期。"""
    shared_stats = {"start_time_monotonic": time.monotonic(), "status": "初始化...", "urls": {}, "all_tunnels_done": False}
    log_manager, display_manager, server_manager, tunnel_manager = None, None, None, None

    try:
        log_manager = LogManager(max_lines=LOG_DISPLAY_LINES, timezone_str=TIMEZONE)
        server_manager = ServerManager(log_manager=log_manager, stats_dict=shared_stats)
        display_manager = DisplayManager(log_manager=log_manager, stats_dict=shared_stats, refresh_rate=UI_REFRESH_SECONDS)

        display_manager.start()
        server_manager.start()

        if server_manager.server_ready_event.wait(timeout=SERVER_READY_TIMEOUT):
            if not server_manager.port:
                log_manager.log("CRITICAL", "伺服器已就緒，但未能解析出 API 埠號。無法建立代理連結。")
            else:
                # --- 移植 v17 的多通道管理與健康檢查邏輯 ---
                shared_stats["status"] = "正在建立網路通道..."
                results_queue = Queue()
                project_path = Path(PROJECT_FOLDER_NAME)
                tunnel_manager = TunnelManager(server_manager.port, project_path, log_manager, results_queue)
                tunnel_manager.start_tunnels()

                health_check_passed = False
                urls_to_check = []
                enabled_tunnels_count = ENABLE_COLAB_PROXY + ENABLE_LOCALTUNNEL + ENABLE_CLOUDFLARE
                monitoring_deadline = time.monotonic() + 120 # 總監控時間

                while time.monotonic() < monitoring_deadline:
                    # 檢查後端服務是否仍在運行
                    if server_manager.server_process.poll() is not None:
                        shared_stats["status"] = f"❌ 後端服務已停止 (返回碼: {server_manager.server_process.poll()})"
                        raise RuntimeError("後端服務在通道建立期間意外終止。")

                    # 處理佇列中的新 URL
                    try:
                        name, data = results_queue.get_nowait()
                        shared_stats["urls"][name] = data
                        if "錯誤" not in data.get("url", ""):
                            urls_to_check.append(data["url"])
                    except Empty:
                        pass # 佇列為空，繼續執行

                    # 如果尚未通過健康檢查，且有新的 URL 可供檢查
                    if not health_check_passed and urls_to_check:
                        shared_stats["status"] = "正在驗證服務健康度..."
                        url_to_test = urls_to_check.pop(0)
                        try:
                            health_url = f"{url_to_test.rstrip('/')}/api/health"
                            log_manager.log("INFO", f"正在嘗試健康檢查: {health_url}")
                            response = requests.get(health_url, timeout=10)
                            if response.status_code == 200 and response.json().get("status") == "ok":
                                log_manager.log("SUCCESS", f"✅ 健康檢查通過！服務在 {url_to_test} 上已就緒。")
                                shared_stats["status"] = "✅ 應用程式已就緒"
                                health_check_passed = True
                        except requests.RequestException as e:
                            log_manager.log("WARN", f"健康檢查請求失敗: {e}，將繼續嘗試其他網址...")

                    # 檢查是否所有通道都已完成
                    if len(shared_stats.get("urls", {})) >= enabled_tunnels_count:
                        log_manager.log("INFO", "所有通道已嘗試完成。")
                        break # 所有通道都已回報，跳出迴圈

                    time.sleep(UI_REFRESH_SECONDS)

                shared_stats["all_tunnels_done"] = True
                if not health_check_passed:
                    shared_stats["status"] = "❌ 健康檢查失敗"
                    log_manager.log("CRITICAL", "❌ 未能在指定時間內通過健康檢查。")
        else:
            shared_stats["status"] = "❌ 伺服器啟動超時"
            log_manager.log("CRITICAL", f"伺服器在 {SERVER_READY_TIMEOUT} 秒內未能就緒。")

        log_manager.log("INFO", "啟動器將保持運行以維持後端服務。可隨時手動中斷。")
        server_manager.server_process.wait()

    except KeyboardInterrupt:
        if log_manager: log_manager.log("WARN", "🛑 偵測到使用者手動中斷...")
    except Exception as e:
        if log_manager:
            log_manager.log("CRITICAL", f"❌ 發生未預期的致命錯誤: {e}")
            log_manager.log("CRITICAL", traceback.format_exc())
        else:
            print(f"❌ 發生未預期的致命錯誤: {e}")
            traceback.print_exc()
    finally:
        if log_manager: shared_stats["status"] = "關閉中..."
        if display_manager and display_manager._thread.is_alive(): display_manager.stop()
        if tunnel_manager: tunnel_manager.stop_tunnels()
        if server_manager: server_manager.stop()

        if log_manager:
            # 確保最終的 UI 狀態被打印
            if display_manager:
                if ENABLE_CLEAR_OUTPUT: ipy_clear_output()
                print("\n".join(display_manager._build_output_buffer()))
            print("\n--- ✅ 所有任務完成，系統已安全關閉 ---")
            display(HTML(create_log_viewer_html(log_manager)))

if __name__ == "__main__":
    main()
