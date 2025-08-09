# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                      ║
# ║    🐦‍🔥 鳳凰之心 - V66 通用啟動器                                 🐦‍🔥 ║
# ║                                                                      ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║                                                                      ║
# ║ - V66 更新日誌:                                                      ║
# ║   - **相容性**：啟動器指向 1.2.1 分支以支援新協調器架構。        ║
# ║   - **版本**：介面版本號與啟動器標題同步更新至 V66。             ║
# ║                                                                      ║
# ╚══════════════════════════════════════════════════════════════════╝

#@title 🐦‍🔥 鳳凰之心 - V66 通用啟動器 { vertical-output: true, display-mode: "form" }
#@markdown ---
#@markdown ### **Part 1: 專案與環境設定**
#@markdown > **設定 Git 倉庫、分支或標籤，以及專案資料夾。**
#@markdown ---
#@markdown **後端程式碼倉庫 (REPOSITORY_URL)**
REPOSITORY_URL = "https://github.com/hsp1234-web/0808.git" #@param {type:"string"}
#@markdown **後端版本分支或標籤 (TARGET_BRANCH_OR_TAG)**
TARGET_BRANCH_OR_TAG = "1.2.3" #@param {type:"string"}
#@markdown **專案資料夾名稱 (PROJECT_FOLDER_NAME)**
PROJECT_FOLDER_NAME = "WEB1" #@param {type:"string"}
#@markdown **強制刷新後端程式碼 (FORCE_REPO_REFRESH)**
FORCE_REPO_REFRESH = True #@param {type:"boolean"}

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
SHOW_LOG_LEVEL_DEBUG = False #@param {type:"boolean"}

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
from IPython.display import clear_output
from google.colab import output as colab_output

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
        self._lock = threading.Lock()
        self.timezone = pytz.timezone(timezone_str)
        self.log_levels_to_show = log_levels_to_show

    def log(self, level: str, message: str):
        with self._lock:
            log_entry = {"timestamp": datetime.now(self.timezone), "level": level.upper(), "message": str(message)}
            self._log_deque.append(log_entry)

    def get_display_logs(self) -> list:
        with self._lock:
            all_logs = list(self._log_deque)
            return [log for log in all_logs if self.log_levels_to_show.get(f"SHOW_LOG_LEVEL_{log['level']}", False)]

    def get_full_history(self) -> list:
        with self._lock:
            return list(self._log_deque)

ANSI_COLORS = {
    "SUCCESS": "\033[32m", "WARN": "\033[33m", "ERROR": "\033[31m",
    "CRITICAL": "\033[31m", "RESET": "\033[0m"
}

def colorize(text, level):
    return f"{ANSI_COLORS.get(level, '')}{text}{ANSI_COLORS['RESET']}"

class DisplayManager:
    """顯示管理器：在背景執行緒中負責繪製純文字動態儀表板。"""
    def __init__(self, log_manager, stats_dict, refresh_rate):
        self._log_manager = log_manager; self._stats = stats_dict
        self._refresh_rate = refresh_rate; self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _build_output_buffer(self) -> list[str]:
        output_buffer = ["🐦‍🔥 鳳凰之心 - V66 作戰指揮中心 🐦‍🔥", ""]
        logs_to_display = self._log_manager.get_display_logs()
        for log in logs_to_display:
            ts, level = log['timestamp'].strftime('%H:%M:%S'), log['level']
            output_buffer.append(f"[{ts}] {colorize(f'[{level:^8}]', level)} {log['message']}")
        if self._stats.get('proxy_url'):
            if logs_to_display: output_buffer.append("")
            output_buffer.append(f"✅ 代理連結已生成: {self._stats['proxy_url']}")
        try:
            import psutil
            cpu, ram = f"{psutil.cpu_percent():5.1f}%", f"{psutil.virtual_memory().percent:5.1f}%"
        except ImportError: cpu, ram = "  N/A ", "  N/A "
        elapsed = time.monotonic() - self._stats.get("start_time_monotonic", time.monotonic())
        mins, secs = divmod(elapsed, 60)
        output_buffer.append("")
        output_buffer.append(f"⏱️ {int(mins):02d}分{int(secs):02d}秒 | 💻 CPU: {cpu} | 🧠 RAM: {ram} | 🔥 狀態: {self._stats.get('status', '初始化...')}")
        return output_buffer

    def _run(self):
        while not self._stop_event.is_set():
            try:
                clear_output(wait=True); print("\n".join(self._build_output_buffer()), flush=True)
                time.sleep(self._refresh_rate)
            except Exception as e: print(f"\nDisplayManager 執行緒發生錯誤: {e}"); time.sleep(5)

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

            # ** 安裝後端依賴 **
            requirements_path = project_path / "requirements.txt"
            if requirements_path.is_file():
                self._log_manager.log("INFO", f"檢測到 requirements.txt，正在安裝依賴...")
                # 在 Colab 環境中，使用 -q 來減少不必要的輸出
                pip_command = [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements_path)]
                install_result = subprocess.run(pip_command, check=False, capture_output=True, text=True, encoding='utf-8')
                if install_result.returncode != 0:
                    self._log_manager.log("CRITICAL", f"依賴安裝失敗:\n{install_result.stderr}")
                    return
                self._log_manager.log("SUCCESS", "✅ 後端依賴安裝完成。")
            else:
                self._log_manager.log("WARN", "未在倉庫中找到 requirements.txt，跳過依賴安裝。")

            # ** 適配新架構: 啟動 orchestrator.py **
            orchestrator_script_path = project_path / "orchestrator.py"
            if not orchestrator_script_path.is_file():
                self._log_manager.log("CRITICAL", f"核心協調器未找到: {orchestrator_script_path}")
                return

            # ** 適配新架構: 不再傳遞 --mock，因為這是生產環境 **
            self._log_manager.log("INFO", "將啟動後端服務...")
            # 注意：這裡不再傳遞 port，因為新架構中 api_server 使用的是固定埠號 8001
            # 修正：由於 cwd 已經是 project_path，這裡的腳本路徑應該是相對於 project_path 的
            # 在 Colab 環境中，我們總是希望以真實模式運行
            launch_command = [sys.executable, "orchestrator.py", "--no-mock"]

            self.server_process = subprocess.Popen(
                launch_command,
                cwd=str(project_path), # 在下載的專案目錄中執行
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                preexec_fn=os.setsid
            )
            self._log_manager.log("INFO", f"協調器子進程已啟動 (PID: {self.server_process.pid})，正在等待握手信號...")

            # ** 適配新架構: 監聽新的握手信號，並從中解析埠號 **
            port_pattern = re.compile(r"API_PORT:\s*(\d+)")
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

# ==============================================================================
# SECTION 2: 核心功能函式
# ==============================================================================

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
    shared_stats = {"start_time_monotonic": time.monotonic(), "status": "初始化...", "proxy_url": None}
    log_manager, display_manager, server_manager = None, None, None
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
                # V65.5: 增強重試邏輯
                max_retries, retry_delay = 10, 3
                for attempt in range(max_retries):
                    try:
                        log_manager.log("INFO", f"正在嘗試取得代理連結... (第 {attempt + 1}/{max_retries} 次)")
                        url = colab_output.eval_js(f'google.colab.kernel.proxyPort({server_manager.port})')
                        if url and url.strip():
                            shared_stats['proxy_url'] = url
                            log_manager.log("SUCCESS", f"✅ 成功取得代理連結！埠號: {server_manager.port}")
                            break # 成功，跳出迴圈
                    except Exception as e:
                        log_manager.log("WARN", f"嘗試失敗: {e}")

                    if not shared_stats.get('proxy_url'):
                        log_manager.log("INFO", f"將於 {retry_delay} 秒後重試...")
                        time.sleep(retry_delay)

                if not shared_stats.get('proxy_url'):
                    shared_stats['status'] = "❌ 取得代理連結失敗"
                    log_manager.log("CRITICAL", f"在 {max_retries} 次嘗試後，仍無法取得有效的代理連結。")
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
        if server_manager: server_manager.stop()
        end_time = datetime.now(pytz.timezone(TIMEZONE))
        if log_manager and display_manager:
            clear_output(); print("\n".join(display_manager._build_output_buffer()))
            print("\n--- ✅ 所有任務完成，系統已安全關閉 ---")
            from IPython.display import display, HTML
            import json
            full_log_history = log_manager.get_full_history()
            js_screen = json.dumps("\n".join(display_manager._build_output_buffer()))
            js_logs = json.dumps("\n".join([f"[{log['timestamp'].isoformat()}] [{log['level']}] {log['message']}" for log in full_log_history]))
            display(HTML(f"""<script>function copyToClipboard(text) {{navigator.clipboard.writeText(text);}}</script>
                <button onclick='copyToClipboard({js_screen})'>📋 複製上方儲存格輸出</button>
                <button onclick='copyToClipboard({js_logs})'>📄 複製完整詳細日誌</button>"""))
            archive_reports(log_manager, start_time, end_time, shared_stats.get('status', '未知'))

if __name__ == "__main__":
    main()
