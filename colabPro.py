# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                      ║
# ║    🐦‍🔥 鳳凰之心 - V20 穩定版通用啟動器                         🐦‍🔥 ║
# ║                                                                      ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║                                                                      ║
# ║ - V20 更新日誌:                                                      ║
# ║   - **啟動修復**：後端版本指向 `861` 分支，解決協調器啟動時的      ║
# ║     資料庫競爭條件 (race condition) 錯誤。                       ║
# ║   - **介面優化**：將在下一階段優化 HTML 日誌複製按鈕的樣式。       ║
# ║                                                                      ║
# ╚══════════════════════════════════════════════════════════════════╝

#@title 🐦‍🔥 鳳凰之心 - V20 穩定版通用啟動器 { vertical-output: true, display-mode: "form" }
#@markdown ---
#@markdown ### **Part 1: 專案與環境設定**
#@markdown > **設定 Git 倉庫、分支或標籤，以及專案資料夾。**
#@markdown ---
#@markdown **後端程式碼倉庫 (REPOSITORY_URL)**
REPOSITORY_URL = "https://github.com/hsp1234-web/0808.git" #@param {type:"string"}
#@markdown **後端版本分支或標籤 (TARGET_BRANCH_OR_TAG)**
TARGET_BRANCH_OR_TAG = "861" #@param {type:"string"}
#@markdown **專案資料夾名稱 (PROJECT_FOLDER_NAME)**
PROJECT_FOLDER_NAME = "wolf_project" #@param {type:"string"}
#@markdown **強制刷新後端程式碼 (FORCE_REPO_REFRESH)**
FORCE_REPO_REFRESH = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### **Part 1.5: 通道啟用設定**
#@markdown > **選擇要啟動的公開存取通道。建議全部啟用以備不時之需。**
#@markdown ---
#@markdown **啟用 Colab 官方代理**
ENABLE_COLAB_PROXY = True #@param {type:"boolean"}
#@markdown **啟用 Localtunnel**
ENABLE_LOCALTUNNEL = True #@param {type:"boolean"}
#@markdown **啟用 Cloudflare**
ENABLE_CLOUDFLARE = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### **Part 2: 儀表板與監控設定**
#@markdown > **設定儀表板的視覺與行為。**
#@markdown ---
#@markdown **儀表板更新頻率 (秒) (UI_REFRESH_SECONDS)**
UI_REFRESH_SECONDS = 0.5 #@param {type:"number"}
#@markdown **日誌顯示行數 (LOG_DISPLAY_LINES)**
LOG_DISPLAY_LINES = 30 #@param {type:"integer"}
#@markdown **時區設定 (TIMEZONE)**
TIMEZONE = "Asia/Taipei" #@param {type:"string"}

#@markdown ---
#@markdown ### **Part 3: 日誌等級可見性**
#@markdown > **勾選您想在儀表板上看到的日誌等級。**
#@markdown ---
SHOW_LOG_LEVEL_BATTLE = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_SUCCESS = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_INFO = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_WARN = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_ERROR = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_CRITICAL = True #@param {type:"boolean"}
SHOW_LOG_LEVEL_DEBUG = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### **Part 4: 報告與歸檔設定**
#@markdown > **設定在任務結束時如何儲存報告。**
#@markdown ---
#@markdown **日誌歸檔資料夾 (LOG_ARCHIVE_ROOT_FOLDER)**
LOG_ARCHIVE_ROOT_FOLDER = "paper" #@param {type:"string"}
#@markdown **伺服器就緒等待超時 (秒) (SERVER_READY_TIMEOUT)**
SERVER_READY_TIMEOUT = 45 #@param {type:"integer"}

#@markdown ---
#@markdown > **設定完成後，點擊此儲存格左側的「執行」按鈕。**
#@markdown ---

# ==============================================================================
# SECTION 0: 環境準備與核心依賴導入
# ==============================================================================
import sys
import subprocess
import socket
import platform
import urllib.request
try:
    import pytz
except ImportError:
    print("正在安裝 pytz...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pytz"])
    import pytz

import os
import shutil
from pathlib import Path
import time
from datetime import datetime
import threading
from collections import deque
import re
import json
import html
from IPython.display import clear_output
from google.colab import output as colab_output, userdata

# ==============================================================================
# SECTION 0.5: 輔助函式 is omitted for brevity
# ==============================================================================

# ==============================================================================
# SECTION 1: 管理器類別定義 (Managers)
# ==============================================================================

class LogManager:
    """日誌管理器：負責記錄、過濾和儲存所有日誌訊息。"""
    def __init__(self, max_lines, timezone_str, log_levels_to_show):
        self._log_deque = deque(maxlen=max_lines)
        self._full_history = []
        self._lock = threading.Lock()
        self.timezone = pytz.timezone(timezone_str)
        self.log_levels_to_show = log_levels_to_show

    def log(self, level: str, message: str, source: str = "SYSTEM"):
        with self._lock:
            log_entry = {"timestamp": datetime.now(self.timezone), "level": level.upper(), "message": str(message), "source": source}
            self._log_deque.append(log_entry)
            self._full_history.append(log_entry)

    def get_display_logs(self) -> list:
        with self._lock:
            all_logs = list(self._log_deque)
            return [log for log in all_logs if self.log_levels_to_show.get(f"SHOW_LOG_LEVEL_{log['level']}", False)]

    def get_full_history(self) -> list:
        with self._lock:
            return self._full_history

ANSI_COLORS = {
    "SUCCESS": "\033[32m", "WARN": "\033[33m", "ERROR": "\033[31m",
    "CRITICAL": "\033[31m", "RESET": "\033[0m"
}

def colorize(text, level):
    return f"{ANSI_COLORS.get(level, '')}{text}{ANSI_COLORS['RESET']}"

class DisplayManager:
    """顯示管理器：在背景執行緒中負責繪製純文字動態儀表板。"""
    def __init__(self, log_manager, stats_dict, refresh_rate):
        self._log_manager = log_manager
        self._stats = stats_dict
        self._refresh_rate = refresh_rate
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _build_output_buffer(self) -> list[str]:
        output_buffer = ["🐦‍🔥 鳳凰之心 - V20 作戰指揮中心 🐦‍🔥", ""]
        logs_to_display = self._log_manager.get_display_logs()
        for log in logs_to_display:
            ts = log['timestamp'].strftime('%H:%M:%S')
            level, msg = log['level'], log['message']
            output_buffer.append(f"[{ts}] {colorize(f'[{level:^8}]', level)} {msg}")

        urls = self._stats.get('urls', {})
        if urls:
            if logs_to_display: output_buffer.append("")
            output_buffer.append("🔗 公開存取網址 (Public URLs):")
            sorted_urls = sorted(urls.items(), key=lambda item: item[1].get('priority', 99))
            for name, url_info in sorted_urls:
                if url_info['status'] == 'ready':
                    line = f"  - {name}: {colorize(url_info['url'], 'SUCCESS')}"
                    if 'password' in url_info:
                        line += f" (密碼: {url_info['password']})"
                    output_buffer.append(line)
                elif url_info['status'] == 'starting':
                    output_buffer.append(f"  - {name}: 正在啟動中...")
                else:
                    output_buffer.append(f"  - {name}: {colorize(url_info.get('error', '發生錯誤'), 'ERROR')}")

        try:
            import psutil
            cpu, ram = f"{psutil.cpu_percent():5.1f}%", f"{psutil.virtual_memory().percent:5.1f}%"
        except ImportError:
            cpu, ram = "  N/A ", "  N/A "
        elapsed = time.monotonic() - self._stats.get("start_time_monotonic", time.monotonic())
        mins, secs = divmod(elapsed, 60)
        output_buffer.append("")
        output_buffer.append(f"⏱️ {int(mins):02d}分{int(secs):02d}秒 | 💻 CPU: {cpu} | 🧠 RAM: {ram} | 🔥 狀態: {self._stats.get('status', '初始化...')}")
        return output_buffer

    def _run(self):
        while not self._stop_event.is_set():
            try:
                clear_output(wait=True)
                print("\n".join(self._build_output_buffer()), flush=True)
                time.sleep(self._refresh_rate)
            except Exception as e:
                self._log_manager.log("ERROR", f"DisplayManager 執行緒發生錯誤: {e}")
                time.sleep(5)

    def start(self): self._thread.start()
    def stop(self): self._stop_event.set(); self._thread.join(timeout=2)

class ServerManager:
    """伺服器管理器：負責啟動、停止和監控 Uvicorn 子進程。"""
    def __init__(self, log_manager, stats_dict):
        self._log_manager = log_manager; self._stats = stats_dict
        self.server_process = None; self.server_ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.port = None # 將在這裡儲存從日誌中解析出的埠號

    def _run(self):
        try:
            self._stats['status'] = "🚀 呼叫核心協調器..."
            self._log_manager.log("BATTLE", "=== 正在呼叫核心協調器 `orchestrator.py` ===")
            project_path = Path(PROJECT_FOLDER_NAME)
            if FORCE_REPO_REFRESH and project_path.exists():
                self._log_manager.log("INFO", f"偵測到舊的專案資料夾 '{project_path}'，正在強制刪除...")
                shutil.rmtree(project_path)

            self._log_manager.log("INFO", f"正在從 Git 下載 (分支: {TARGET_BRANCH_OR_TAG})...")
            git_command = ["git", "clone", "--branch", TARGET_BRANCH_OR_TAG, "--depth", "1", REPOSITORY_URL, str(project_path)]
            result = subprocess.run(git_command, check=False, capture_output=True, text=True, encoding='utf-8')
            if result.returncode != 0: self._log_manager.log("CRITICAL", f"Git clone 失敗:\n{result.stderr}"); return

            self._log_manager.log("INFO", "✅ Git 倉庫下載完成。")

            # 動態將下載專案的 src 目錄加入 sys.path，以符合新架構
            project_src_path = project_path / "src"
            project_src_path_str = str(project_src_path.resolve())
            if project_src_path_str not in sys.path:
                sys.path.insert(0, project_src_path_str)

            from db.database import initialize_database, add_system_log
            initialize_database()
            add_system_log("colab_setup", "INFO", "Git repository cloned successfully.")

            # --- 啟動流程優化 (2025-08-11) ---
            # 採用「混合式安裝」策略，以最快速度讓伺服器上線

            # 1. 安裝輕量的核心伺服器依賴 (使用 pip)
            server_reqs_path = project_path / "requirements-server.txt"
            if server_reqs_path.is_file():
                self._log_manager.log("INFO", "步驟 1/3: 正在快速安裝核心伺服器依賴...")
                add_system_log("colab_setup", "INFO", "Installing server dependencies...")
                pip_command = [sys.executable, "-m", "pip", "install", "-q", "-r", str(server_reqs_path)]
                install_result = subprocess.run(pip_command, check=False, capture_output=True, text=True, encoding='utf-8')
                if install_result.returncode != 0:
                    self._log_manager.log("CRITICAL", f"核心依賴安裝失敗:\n{install_result.stderr}")
                    add_system_log("colab_setup", "CRITICAL", f"Server dependency installation failed: {install_result.stderr}")
                    return
                self._log_manager.log("SUCCESS", "✅ 核心依賴安裝完成。")
                add_system_log("colab_setup", "SUCCESS", "Server dependencies installed.")
            else:
                self._log_manager.log("WARN", "未找到 requirements-server.txt，跳過核心依賴安裝。")

            # 2. 立刻啟動核心協調器，讓 API 服務上線
            self._log_manager.log("INFO", "步驟 2/3: 正在啟動後端服務...")
            orchestrator_script_path = project_path / "src" / "core" / "orchestrator.py"
            if not orchestrator_script_path.is_file():
                self._log_manager.log("CRITICAL", f"核心協調器未找到: {orchestrator_script_path}")
                return

            # ** 適配新架構: 不再傳遞 --mock，因為這是生產環境 **
            self._log_manager.log("INFO", "將啟動後端服務...")

            # --- JULES 於 2025-08-10 的修復 ---
            # 在啟動前，先清理上一次執行可能遺留的 port 檔案，避免讀取到過期的埠號
            port_file_path = project_path / "src" / "db" / "db_manager.port"
            if port_file_path.exists():
                self._log_manager.log("WARN", f"偵測到舊的埠號檔案，正在清理: {port_file_path}")
                try:
                    port_file_path.unlink()
                except Exception as e:
                    self._log_manager.log("ERROR", f"清理舊的埠號檔案時發生錯誤: {e}")
            # --- 修復結束 ---

            # 注意：這裡不再傳遞 port，因為新架構中 api_server 使用的是固定埠號 8001
            # 修正：由於 cwd 已經是 project_path，這裡的腳本路徑應該是相對於 project_path 的
            # 在 Colab 環境中，我們總是希望以真實模式運行
            launch_command = [sys.executable, "src/core/orchestrator.py", "--no-mock"]

            # --- JULES 於 2025-08-10 的修改與增強：從 Colab Secrets 或 config.json 讀取 API 金鑰 ---
            process_env = os.environ.copy()
            google_api_key = None
            key_source = None

            # 1. 優先從 Colab Secrets 讀取金鑰
            try:
                key_from_secret = userdata.get('GOOGLE_API_KEY')
                if key_from_secret:
                    google_api_key = key_from_secret
                    key_source = "Colab Secret"
            except Exception as e:
                self._log_manager.log("WARN", f"讀取 Colab Secret 時發生錯誤: {e}。將嘗試從 config.json 讀取。")

            # 2. 如果 Colab Secrets 中沒有，則從 config.json 讀取
            if not google_api_key:
                config_path = project_path / "config.json"
                if config_path.is_file():
                    try:
                        self._log_manager.log("INFO", "正在嘗試從 config.json 讀取 API 金鑰...")
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)

                        key_from_config = config_data.get("GOOGLE_API_KEY")
                        api_key_placeholder = "在此處填入您的 GOOGLE API 金鑰"

                        if key_from_config and key_from_config != api_key_placeholder:
                            google_api_key = key_from_config
                            key_source = "config.json"
                    except (json.JSONDecodeError, IOError) as e:
                        self._log_manager.log("ERROR", f"讀取或解析 config.json 時發生錯誤: {e}")

            # 3. 根據讀取結果設定環境變數或顯示警告
            if google_api_key:
                process_env['GOOGLE_API_KEY'] = google_api_key
                self._log_manager.log("SUCCESS", f"✅ 成功從 {key_source} 讀取 GOOGLE_API_KEY 並設定為環境變數。")
            else:
                self._log_manager.log("WARN", "⚠️ 在 Colab Secrets 和 config.json 中均未找到有效的 GOOGLE_API_KEY。")
                self._log_manager.log("WARN", "YouTube 相關功能將被停用。請設定 Colab Secret 或在專案中提供 config.json 以啟用完整功能。")
            # --- 金鑰讀取邏輯結束 ---

            # --- JULES'S FINAL FIX (2025-08-15) ---
            # 明確設定 PYTHONPATH，以解決子進程中的 ModuleNotFoundError。
            # 這是確保子進程找到模組最可靠的方法。
            src_path_str = str((project_path / "src").resolve())
            existing_python_path = process_env.get('PYTHONPATH', '')
            process_env['PYTHONPATH'] = f"{src_path_str}{os.pathsep}{existing_python_path}".strip(os.pathsep)
            self._log_manager.log("INFO", f"正在設定子程序的 PYTHONPATH: {process_env['PYTHONPATH']}")
            # --- 修正結束 ---

            self.server_process = subprocess.Popen(
                launch_command,
                cwd=str(project_path), # 在下載的專案目錄中執行
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                preexec_fn=os.setsid,
                env=process_env # 將包含 API 金鑰的環境變數傳遞給子程序
            )
            self._log_manager.log("INFO", f"協調器子進程已啟動 (PID: {self.server_process.pid})，正在等待握手信號...")

            # 3. 在背景執行緒中安裝大型依賴 (使用 uv)
            worker_reqs_path = project_path / "requirements-worker.txt"
            background_install_thread = threading.Thread(
                target=self._install_worker_deps,
                args=(worker_reqs_path,),
                daemon=True
            )
            background_install_thread.start()

            # ** 適配新架構: 監聽新的握手信號，並從中解析埠號 **
            # JULES' FIX (2025-08-10): 更新 정규표현식 以匹配 'PROXY_URL:' 格式
            port_pattern = re.compile(r"PROXY_URL: http://127.0.0.1:(\d+)")
            uvicorn_ready_pattern = re.compile(r"Uvicorn running on")
            server_ready = False

            for line in iter(self.server_process.stdout.readline, ''):
                if self._stop_event.is_set(): break

                line = line.strip()
                self._log_manager.log("DEBUG", line) # 顯示所有日誌

                # 解析埠號
                if not self.port:
                    port_match = port_pattern.search(line)
                    if port_match:
                        self.port = int(port_match.group(1))
                        self._log_manager.log("INFO", f"✅ 從日誌中成功解析出 API 埠號: {self.port}")

                # 監聽 Uvicorn 就緒信號
                if not server_ready:
                    if uvicorn_ready_pattern.search(line):
                        server_ready = True
                        self._stats['status'] = "✅ 伺服器運行中"
                        self._log_manager.log("SUCCESS", "伺服器已就緒！收到 Uvicorn 握手信號！")

                # 當埠號和就緒信號都收到後，才觸發事件
                if self.port and server_ready:
                    self.server_ready_event.set()
                    # 這裡可以選擇性 break，但為了持續監控，我們讓它繼續讀取日誌

            # 等待子程序自然結束 (通常是外部中斷)
            self.server_process.wait()

            # 如果事件從未被設定，表示程序在就緒前就已終止
            if not self.server_ready_event.is_set():
                self._stats['status'] = "❌ 伺服器啟動失敗"
                self._log_manager.log("CRITICAL", "協調器進程在就緒前已終止。")
        except Exception as e: self._stats['status'] = "❌ 發生致命錯誤"; self._log_manager.log("CRITICAL", f"ServerManager 執行緒出錯: {e}")
        finally: self._stats['status'] = "⏹️ 已停止"

    def _install_worker_deps(self, requirements_path: Path):
        """在背景安裝大型 Worker 依賴項。"""
        try:
            self._log_manager.log("INFO", "步驟 3/3: [背景] 開始安裝大型任務依賴...")
            if not requirements_path.is_file():
                self._log_manager.log("WARN", f"[背景] 未找到 {requirements_path.name}，跳過大型依賴安裝。")
                return

            # 安裝 uv
            self._log_manager.log("INFO", "[背景] 正在安裝 uv 加速器...")
            pip_install_uv_cmd = [sys.executable, "-m", "pip", "install", "-q", "uv"]
            uv_install_result = subprocess.run(pip_install_uv_cmd, check=False, capture_output=True, text=True, encoding='utf-8')
            if uv_install_result.returncode != 0:
                self._log_manager.log("ERROR", f"[背景] uv 安裝失敗:\n{uv_install_result.stderr}")
                return
            self._log_manager.log("INFO", "[背景] ✅ uv 安裝成功。")

            # 使用 uv 安裝 worker 依賴
            self._log_manager.log("INFO", "[背景] 正在使用 uv 加速安裝大型依賴...")
            uv_pip_install_cmd = [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", str(requirements_path)]
            worker_install_result = subprocess.run(uv_pip_install_cmd, check=False, capture_output=True, text=True, encoding='utf-8')
            if worker_install_result.returncode != 0:
                self._log_manager.log("ERROR", f"[背景] 大型依賴安裝失敗:\n{worker_install_result.stderr}")
                return

            self._log_manager.log("SUCCESS", "[背景] ✅ 所有大型任務依賴均已成功安裝！")
        except Exception as e:
            self._log_manager.log("CRITICAL", f"[背景] 安裝執行緒發生未預期錯誤: {e}")

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
    """通道管理器：並行啟動多個代理通道 (Cloudflare, Localtunnel) 以提供備援。"""
    def __init__(self, log_manager, stats_dict, port):
        self._log = log_manager
        self._stats = stats_dict
        self._port = port
        self._stop_event = threading.Event()
        self._threads = []
        self._processes = []

    def start(self):
        if ENABLE_CLOUDFLARE: self._start_thread(self._run_cloudflared, "Cloudflare")
        if ENABLE_LOCALTUNNEL: self._start_thread(self._run_localtunnel, "Localtunnel")
        if ENABLE_COLAB_PROXY: self._start_thread(self._run_colab_proxy, "Colab")

    def _start_thread(self, target, name):
        thread = threading.Thread(target=target, name=name, daemon=True)
        self._threads.append(thread)
        thread.start()

    def _update_url_status(self, name, status, url=None, error=None, priority=99, password=None):
        with self._stats.get('_lock', threading.Lock()):
            entry = {"status": status, "priority": priority}
            if url: entry["url"] = url
            if error: entry["error"] = error
            if password: entry["password"] = password
            self._stats.setdefault('urls', {})[name] = entry

    def _ensure_cloudflared_installed(self):
        if Path("./cloudflared").is_file(): return True
        self._log.log("INFO", "未找到 Cloudflared，正在下載...", "Cloudflare")
        arch = platform.machine()
        if arch == "x86_64": url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        elif arch == "aarch64": url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
        else: self._log.log("ERROR", f"不支援的架構: {arch}", "Cloudflare"); return False
        try:
            urllib.request.urlretrieve(url, "cloudflared")
            os.chmod("cloudflared", 0o755)
            self._log.log("SUCCESS", "✅ Cloudflared 下載成功。", "Cloudflare")
            return True
        except Exception as e: self._log.log("ERROR", f"Cloudflared 下載失敗: {e}", "Cloudflare"); return False

    def _run_cloudflared(self):
        self._update_url_status("Cloudflare", "starting", priority=2)
        if not self._ensure_cloudflared_installed():
            self._update_url_status("Cloudflare", "error", error="安裝失敗")
            return

        command = ["./cloudflared", "tunnel", "--url", f"http://127.0.0.1:{self._port}"]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        self._processes.append(proc)

        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        for line in iter(proc.stdout.readline, ''):
            if self._stop_event.is_set(): break
            self._log.log("DEBUG", line.strip(), "Cloudflare")
            match = url_pattern.search(line)
            if match:
                self._update_url_status("Cloudflare", "ready", url=match.group(0), priority=2)
                break
        else:
            if not self._stop_event.is_set():
                self._update_url_status("Cloudflare", "error", error="無法從日誌中解析 URL")

    def _ensure_localtunnel_installed(self):
        result = subprocess.run(["npm", "list", "-g", "localtunnel"], capture_output=True, text=True)
        if "localtunnel@" in result.stdout: return True
        self._log.log("INFO", "正在安裝 Localtunnel...", "Localtunnel")
        try:
            subprocess.run(["npm", "install", "-g", "localtunnel"], check=True, capture_output=True, text=True)
            self._log.log("SUCCESS", "✅ Localtunnel 安裝成功。", "Localtunnel")
            return True
        except subprocess.CalledProcessError as e:
            self._log.log("ERROR", f"Localtunnel 安裝失敗: {e.stderr}", "Localtunnel")
            return False

    def _run_localtunnel(self):
        self._update_url_status("Localtunnel", "starting", priority=3)
        if not self._ensure_localtunnel_installed():
            self._update_url_status("Localtunnel", "error", error="安裝失敗")
            return

        command = ["npx", "localtunnel", "--port", str(self._port)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        self._processes.append(proc)

        url_pattern = re.compile(r"your url is: (https://[a-zA-Z0-9-]+\.loca\.lt)")
        for line in iter(proc.stdout.readline, ''):
            if self._stop_event.is_set(): break
            self._log.log("DEBUG", line.strip(), "Localtunnel")
            match = url_pattern.search(line)
            if match:
                self._update_url_status("Localtunnel", "ready", url=match.group(1), priority=3)
                break
        else:
            if not self._stop_event.is_set():
                self._update_url_status("Localtunnel", "error", error="無法從日誌中解析 URL")

    def _run_colab_proxy(self):
        self._update_url_status("Colab", "starting", priority=1)
        max_retries, retry_delay = 10, 2
        for attempt in range(max_retries):
            if self._stop_event.is_set(): return
            try:
                url = colab_output.eval_js(f'google.colab.kernel.proxyPort({self._port})', timeout_sec=10)
                if url and url.strip():
                    self._update_url_status("Colab", "ready", url=url, priority=1)
                    return
                self._log.log("WARN", f"Colab 代理嘗試 #{attempt+1} 返回空 URL。", "Colab")
            except Exception as e:
                self._log.log("WARN", f"Colab 代理嘗試 #{attempt+1} 失敗: {e}", "Colab")
            time.sleep(retry_delay)
        self._update_url_status("Colab", "error", error=f"重試 {max_retries} 次後失敗")

    def stop(self):
        self._stop_event.set()
        for p in self._processes:
            if p.poll() is None:
                try: p.terminate()
                except ProcessLookupError: pass
        for t in self._threads:
            t.join(timeout=2)


# ==============================================================================
# SECTION 2: 核心功能函式
# ==============================================================================

def create_log_viewer_html(log_manager, display_manager):
    """ 產生最終的 HTML 日誌報告，樣式與 v17 版本一致。 """
    try:
        # Get logs for display
        full_log_history = log_manager.get_full_history()
        log_to_copy = [f"[{log['timestamp'].isoformat()}] [{log['level']}] {log['message']}" for log in full_log_history]

        # Get screen output for display
        screen_output = "\n".join(display_manager._build_output_buffer())

        num_logs = len(log_to_copy)

        # Escape for HTML
        # Taking only the last 10000 characters for display to avoid browser freeze
        escaped_log_for_display = html.escape("\n".join(log_to_copy)[-10000:])

        # Prepare for JavaScript
        escaped_log_for_js = json.dumps("\n".join(log_to_copy))
        escaped_screen_for_js = json.dumps(screen_output)

        return f'''
            <style>
                .collapsible-log {{ margin-top: 15px; margin-bottom: 15px; border: 1px solid #e0e0e0; padding: 12px; border-radius: 8px; background-color: #fafafa; }}
                .collapsible-log summary {{ cursor: pointer; font-weight: bold; color: #333; }}
                .collapsible-log pre {{ background-color: #fff; padding: 12px; border: 1px solid #e0e0e0; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 13px; color: #444; max-height: 400px; overflow-y: auto; }}
                .copy-button {{ padding: 8px 16px; margin: 5px; cursor: pointer; border: 1px solid #ccc; border-radius: 5px; background-color: #f0f0f0; font-family: sans-serif; }}
                .copy-button:hover {{ background-color: #e0e0e0; }}
            </style>
            <script>
                function copyLogToClipboard(text, button) {{
                    navigator.clipboard.writeText(text).then(() => {{
                        const originalText = button.innerText;
                        button.innerText = "✅ 已複製!";
                        setTimeout(() => {{ button.innerText = originalText; }}, 2000);
                    }}, (err) => {{
                        button.innerText = "❌ 複製失敗";
                        console.error('複製失敗: ', err);
                    }});
                }}
            </script>
            <div>
                <button class="copy-button" onclick="copyLogToClipboard({escaped_screen_for_js}, this)">📋 複製上方最終畫面</button>
            </div>
            <details class="collapsible-log">
                <summary>點此展開/收合最近 {num_logs} 條詳細日誌</summary>
                <div style="margin-top: 12px;">
                    <button class="copy-button" onclick="copyLogToClipboard({escaped_log_for_js}, this)">📄 複製下方完整日誌</button>
                    <pre><code>{escaped_log_for_display}</code></pre>
                    <button class="copy-button" onclick="copyLogToClipboard({escaped_log_for_js}, this)">📄 複製下方完整日誌</button>
                </div>
            </details>
        '''
    except Exception as e:
        return f"<p>❌ 產生最終日誌報告時發生錯誤: {html.escape(str(e))}</p>"

def archive_reports(log_manager, start_time, end_time, status):
    print("\n\n" + "="*60 + "\n--- 任務結束，開始執行自動歸檔 ---\n" + "="*60)
    try:
        root_folder = Path(LOG_ARCHIVE_ROOT_FOLDER)
        root_folder.mkdir(exist_ok=True)
        ts_folder_name = start_time.strftime('%Y-%m-%dT%H-%M-%S%z')
        report_dir = root_folder / ts_folder_name
        report_dir.mkdir(exist_ok=True)
        log_history = log_manager.get_full_history()
        detailed_log_content = f"# 詳細日誌\n\n```\n" + "\n".join([f"[{log['timestamp'].isoformat()}] [{log['level']}] {log['message']}" for log in log_history]) + "\n```"
        (report_dir / "詳細日誌.md").write_text(detailed_log_content, encoding='utf-8')
        duration = end_time - start_time
        perf_report_content = f"# 效能報告\n\n- **任務狀態**: {status}\n- **開始時間**: `{start_time.isoformat()}`\n- **結束時間**: `{end_time.isoformat()}`\n- **總耗時**: `{str(duration)}`\n"
        (report_dir / "效能報告.md").write_text(perf_report_content.strip(), encoding='utf-8')
        (report_dir / "綜合報告.md").write_text(f"# 綜合報告\n\n{perf_report_content}\n{detailed_log_content}", encoding='utf-8')
        print(f"✅ 報告已成功歸檔至: {report_dir}")
    except Exception as e: print(f"❌ 歸檔報告時發生錯誤: {e}")

# ==============================================================================
# SECTION 2.5: 安裝系統級依賴 (FFmpeg)
# ==============================================================================
print("檢查並安裝系統級依賴 FFmpeg...")
try:
    ffmpeg_check = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if ffmpeg_check.returncode != 0:
        print("未偵測到 FFmpeg，開始安裝...")
        subprocess.run(["apt-get", "update", "-qq"], check=True)
        subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=True)
        print("✅ FFmpeg 安裝完成。")
    else:
        print("✅ FFmpeg 已安裝。")
except Exception as e:
    print(f"❌ 安裝 FFmpeg 時發生錯誤: {e}")

# ==============================================================================
# SECTION 3: 主程式執行入口
# ==============================================================================

def main():
    """主執行函式，負責初始化管理器、協調流程並處理生命週期。"""
    shared_stats = {
        "start_time_monotonic": time.monotonic(),
        "status": "初始化...",
        "urls": {}
    }
    log_manager, display_manager, server_manager, tunnel_manager = None, None, None, None
    start_time = datetime.now(pytz.timezone(TIMEZONE))
    try:
        log_levels = {name: globals()[name] for name in globals() if name.startswith("SHOW_LOG_LEVEL_")}
        log_manager = LogManager(max_lines=LOG_DISPLAY_LINES, timezone_str=TIMEZONE, log_levels_to_show=log_levels)
        server_manager = ServerManager(log_manager=log_manager, stats_dict=shared_stats)
        display_manager = DisplayManager(log_manager=log_manager, stats_dict=shared_stats, refresh_rate=UI_REFRESH_SECONDS)

        display_manager.start()
        server_manager.start()

        if server_manager.server_ready_event.wait(timeout=SERVER_READY_TIMEOUT):
            if not server_manager.port:
                log_manager.log("CRITICAL", "伺服器已就緒，但未能解析出 API 埠號。無法建立代理連結。")
            else:
                log_manager.log("SUCCESS", f"✅ 後端服務已在埠號 {server_manager.port} 上就緒，正在啟動所有代理通道...")
                tunnel_manager = TunnelManager(
                    log_manager=log_manager,
                    stats_dict=shared_stats,
                    port=server_manager.port
                )
                tunnel_manager.start()
        else:
            shared_stats['status'] = "❌ 伺服器啟動超時"
            log_manager.log("CRITICAL", f"伺服器在 {SERVER_READY_TIMEOUT} 秒內未能就緒。")

        while server_manager._thread.is_alive(): time.sleep(1)
    except KeyboardInterrupt:
        if log_manager: log_manager.log("WARN", "🛑 偵測到使用者手動中斷...")
    except Exception as e:
        if log_manager: log_manager.log("CRITICAL", f"❌ 發生未預期的致命錯誤: {e}")
        else: print(f"❌ 發生未預期的致命錯誤: {e}")
    finally:
        if display_manager and display_manager._thread.is_alive(): display_manager.stop()
        if 'tunnel_manager' in locals() and tunnel_manager: tunnel_manager.stop()
        if server_manager: server_manager.stop()
        end_time = datetime.now(pytz.timezone(TIMEZONE))
        if log_manager and display_manager:
            clear_output(); print("\n".join(display_manager._build_output_buffer()))
            print("\n--- ✅ 所有任務完成，系統已安全關閉 ---")
            from IPython.display import display, HTML
            import json
            display(HTML(create_log_viewer_html(log_manager, display_manager)))
            archive_reports(log_manager, start_time, end_time, shared_stats.get('status', '未知'))

if __name__ == "__main__":
    main()
