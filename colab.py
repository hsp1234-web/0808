# -*- coding: utf-8 -*-
# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                      ║
# ║    🐦‍🔥 鳳凰之心 - V2.0 健壯版啟動器                             🐦‍🔥 ║
# ║                                                                      ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║                                                                      ║
# ║ - V2.0 更新日誌:                                                     ║
# ║   - **模式切換**: 新增「使用本地程式碼」選項，無需強制 Git 下載。  ║
# ║   - **穩定輸出**: 伺服器就緒後，停止儀表板刷新，提供清晰可點擊連結。║
# ║   - **看門狗**: 新增閒置超時自動關閉功能，節省 Colab 資源。        ║
# ║   - **架構**: 參考 BUG.md，採用更穩健的 `subprocess.run` 啟動方式。║
# ║                                                                      ║
# ╚══════════════════════════════════════════════════════════════════╝

#@title 🐦‍🔥 鳳凰之心 - V2.0 健壯版啟動器 { vertical-output: true, display-mode: "form" }
#@markdown ---
#@markdown ### **Part 1: 執行模式**
#@markdown > **選擇程式碼的來源。**
#@markdown ---
#@markdown **✅ 使用本地程式碼 (推薦)**
#@markdown > **勾選此項，將直接執行當前環境中的程式碼。**
#@markdown > **取消勾選，則會從下面的 Git 倉庫下載指定版本的程式碼。**
USE_LOCAL_CODE = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### **Part 2: Git 遠端設定 (僅在不使用本地程式碼時生效)**
#@markdown > **設定 Git 倉庫、分支或標籤，以及專案資料夾。**
#@markdown ---
#@markdown **後端程式碼倉庫 (REPOSITORY_URL)**
REPOSITORY_URL = "https://github.com/hsp1234-web/0808.git" #@param {type:"string"}
#@markdown **後端版本分支或標籤 (TARGET_BRANCH_OR_TAG)**
TARGET_BRANCH_OR_TAG = "1.1.3" #@param {type:"string"}
#@markdown **專案資料夾名稱 (PROJECT_FOLDER_NAME)**
PROJECT_FOLDER_NAME = "WEB1" #@param {type:"string"}
#@markdown **強制刷新後端程式碼 (FORCE_REPO_REFRESH)**
FORCE_REPO_REFRESH = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### **Part 3: 儀表板與監控設定**
#@markdown > **設定儀表板、看門狗與日誌。**
#@markdown ---
#@markdown **閒置超時自動關閉 (秒) (IDLE_TIMEOUT_SECONDS)**
#@markdown > **伺服器在無任務處理且閒置超過此時間後，將自動關閉。設為 0 可禁用。**
IDLE_TIMEOUT_SECONDS = 120 #@param {type:"integer"}
#@markdown **儀表板更新頻率 (秒) (UI_REFRESH_SECONDS)**
UI_REFRESH_SECONDS = 1 #@param {type:"number"}
#@markdown **日誌顯示行數 (LOG_DISPLAY_LINES)**
LOG_DISPLAY_LINES = 30 #@param {type:"integer"}
#@markdown **伺服器就緒等待超時 (秒) (SERVER_READY_TIMEOUT)**
SERVER_READY_TIMEOUT = 60 #@param {type:"integer"}
#@markdown **時區設定 (TIMEZONE)**
TIMEZONE = "Asia/Taipei" #@param {type:"string"}
#@markdown **日誌歸檔資料夾 (LOG_ARCHIVE_ROOT_FOLDER)**
LOG_ARCHIVE_ROOT_FOLDER = "paper" #@param {type:"string"}

#@markdown ---
#@markdown > **設定完成後，點擊此儲存格左側的「執行」按鈕。**
#@markdown ---

# ==============================================================================
# SECTION 0: 環境準備與核心依賴導入
# ==============================================================================
import sys
import subprocess
import socket
import shutil
import time
import threading
import os
from pathlib import Path
from collections import deque
from datetime import datetime
from IPython.display import clear_output, display, HTML

try:
    import pytz
except ImportError:
    print("正在安裝 pytz...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pytz"])
    import pytz

from google.colab import output as colab_output

# ==============================================================================
# SECTION 0.5: 輔助函式與日誌管理器
# ==============================================================================
def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0)); return s.getsockname()[1]

class LogManager:
    def __init__(self, max_lines, timezone_str):
        self._log_deque = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self.timezone = pytz.timezone(timezone_str)
    def log(self, level: str, message: str):
        with self._lock:
            self._log_deque.append({"timestamp": datetime.now(self.timezone), "level": level.upper(), "message": str(message)})
    def get_display_logs(self) -> list:
        with self._lock: return list(self._log_deque)

# ==============================================================================
# SECTION 1: 管理器類別定義 (Managers)
# ==============================================================================

class DisplayManager:
    def __init__(self, log_manager, stats_dict, refresh_rate):
        self._log_manager, self._stats, self._refresh_rate = log_manager, stats_dict, refresh_rate
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _build_output_buffer(self) -> list[str]:
        output_buffer = ["🐦‍🔥 **鳳凰之心 v2.0 - 作戰指揮中心** 🐦‍🔥", "---"]
        for log in self._log_manager.get_display_logs():
            ts, level, msg = log['timestamp'].strftime('%H:%M:%S'), log['level'], log['message']
            output_buffer.append(f"[{ts}] [{level:^8}] {msg}")
        if self._stats.get('proxy_url'):
            output_buffer.append("---")
            output_buffer.append(f"✅ **代理連結已生成**: {self._stats['proxy_url']}")

        elapsed = time.monotonic() - self._stats.get("start_time_monotonic", time.monotonic())
        mins, secs = divmod(elapsed, 60)

        try:
            # 嘗試導入 psutil 並獲取系統狀態
            import psutil
            cpu_percent = f"{psutil.cpu_percent():5.1f}%"
            ram_percent = f"{psutil.virtual_memory().percent:5.1f}%"
        except (ImportError, FileNotFoundError):
            cpu_percent, ram_percent = "N/A", "N/A"

        status_line = f"⏱️ {int(mins):02d}分{int(secs):02d}秒 | 💻 CPU: {cpu_percent} | 🧠 RAM: {ram_percent} | 🔥 狀態: {self._stats.get('status', '初始化...')}"

        if (timeout := self._stats.get("idle_timeout_countdown")) is not None:
            status_line += f" | 😴 閒置關閉倒數: {int(timeout)}s"

        output_buffer.append("---")
        output_buffer.append(status_line)
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
    def __init__(self, log_manager, stats_dict):
        self._log_manager, self._stats = log_manager, stats_dict
        self.server_process = None
        self.server_ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.port = find_free_port()

    def _run(self):
        try:
            # 根據模式決定專案的根目錄
            if not USE_LOCAL_CODE:
                self._stats['status'] = "🚀 準備從 Git 下載..."
                project_path = Path(PROJECT_FOLDER_NAME)
                if FORCE_REPO_REFRESH and project_path.exists():
                    self._log_manager.log("INFO", f"偵測到舊的專案資料夾 '{project_path}'，正在強制刪除...")
                    shutil.rmtree(project_path)

                self._log_manager.log("INFO", f"正在從 Git 下載 (分支: {TARGET_BRANCH_OR_TAG})...")
                git_command = ["git", "clone", "--branch", TARGET_BRANCH_OR_TAG, "--depth", "1", REPOSITORY_URL, str(project_path)]
                result = subprocess.run(git_command, check=False, capture_output=True, text=True, encoding='utf-8')
                if result.returncode != 0:
                    self._log_manager.log("CRITICAL", f"Git clone 失敗:\n{result.stderr}"); return
                self._log_manager.log("INFO", "✅ Git 倉庫下載完成。")
            else:
                self._log_manager.log("INFO", "✅ 使用本地程式碼模式，跳過 Git 下載。")
                # 修正：在本地模式下，專案路徑固定為 /app，以避免 CWD 問題
                project_path = Path("/app")

            # --- 檔案存在性除錯 ---
            self._log_manager.log("DEBUG", f"正在檢查專案路徑: {project_path.resolve()}")
            try:
                ls_output = subprocess.run(["ls", "-lR", str(project_path)], capture_output=True, text=True, encoding='utf-8')
                self._log_manager.log("DEBUG", f"'{project_path}' 目錄內容:\n{ls_output.stdout}\n{ls_output.stderr}")
            except Exception as e:
                self._log_manager.log("WARN", f"無法列出目錄 '{project_path}': {e}")

            launcher_script = Path("scripts") / "launch.py"
            full_launcher_path = project_path / launcher_script

            if not full_launcher_path.is_file():
                self._log_manager.log("CRITICAL", f"核心啟動器未找到: {full_launcher_path.resolve()}"); return

            self._stats['status'] = "🚀 呼叫核心啟動器..."
            self._log_manager.log("BATTLE", f"=== 正在呼叫核心啟動器 `{full_launcher_path}` ===")
            self._log_manager.log("INFO", f"將在動態埠號 {self.port} 上啟動服務。")

            # 在命令中使用相對於 cwd 的路徑
            launch_command = [sys.executable, str(launcher_script), "--port", str(self.port)]

            self.server_process = subprocess.Popen(
                launch_command, cwd=str(project_path),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', preexec_fn=os.setsid
            )
            self._log_manager.log("INFO", f"子進程已啟動 (PID: {self.server_process.pid})，正在等待握手信號...")

            for line in iter(self.server_process.stdout.readline, ''):
                if self._stop_event.is_set(): break
                self._log_manager.log("DEBUG", line.strip())
                self._stats['last_activity_time'] = time.monotonic()
                if "PHOENIX_SERVER_READY_FOR_COLAB" in line:
                    self._stats['status'] = "✅ 伺服器運行中"
                    self._log_manager.log("SUCCESS", "伺服器已就緒！收到握手信號！")
                    self.server_ready_event.set()

            self.server_process.wait()
            if not self.server_ready_event.is_set():
                 self._stats['status'] = "❌ 伺服器啟動失敗"
                 self._log_manager.log("CRITICAL", "伺服器進程在就緒前已終止。")

        except Exception as e:
            self._stats['status'] = "❌ 發生致命錯誤"
            self._log_manager.log("CRITICAL", f"ServerManager 執行緒出錯: {e}")
        finally:
            self._stats['status'] = "⏹️ 已停止"
            self._stop_event.set()

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
    """將本次執行的日誌與效能報告歸檔儲存。"""
    print("\n\n" + "="*60 + "\n--- 任務結束，開始執行自動歸檔 ---\n" + "="*60)
    try:
        root_folder = Path(LOG_ARCHIVE_ROOT_FOLDER)
        root_folder.mkdir(exist_ok=True)
        ts_folder_name = start_time.strftime('%Y-%m-%dT%H-%M-%S%z')
        report_dir = root_folder / ts_folder_name
        report_dir.mkdir(exist_ok=True)

        # 使用 LogManager 的 get_display_logs 獲取的是字典列表，需要格式化
        log_history = log_manager.get_display_logs()
        formatted_logs = [f"[{log['timestamp'].isoformat()}] [{log['level']}] {log['message']}" for log in log_history]
        detailed_log_content = f"# 詳細日誌\n\n```\n" + "\n".join(formatted_logs) + "\n```"
        (report_dir / "詳細日誌.md").write_text(detailed_log_content, encoding='utf-8')

        duration = end_time - start_time
        perf_report_content = f"# 效能報告\n\n- **任務狀態**: {status}\n- **開始時間**: `{start_time.isoformat()}`\n- **結束時間**: `{end_time.isoformat()}`\n- **總耗時**: `{str(duration)}`\n"
        (report_dir / "效能報告.md").write_text(perf_report_content.strip(), encoding='utf-8')
        (report_dir / "綜合報告.md").write_text(f"# 綜合報告\n\n{perf_report_content}\n{detailed_log_content}", encoding='utf-8')
        print(f"✅ 報告已成功歸檔至: {report_dir}")
    except Exception as e:
        print(f"❌ 歸檔報告時發生錯誤: {e}")

# ==============================================================================
# SECTION 3: 主程式執行入口
# ==============================================================================

def main():
    shared_stats = {
        "start_time_monotonic": time.monotonic(),
        "last_activity_time": time.monotonic(),
        "status": "初始化...",
        "proxy_url": None,
        "idle_timeout_countdown": None
    }
    log_manager = LogManager(max_lines=LOG_DISPLAY_LINES, timezone_str=TIMEZONE)
    server_manager = ServerManager(log_manager=log_manager, stats_dict=shared_stats)
    display_manager = DisplayManager(log_manager=log_manager, stats_dict=shared_stats, refresh_rate=UI_REFRESH_SECONDS)

    start_time = datetime.now(pytz.timezone(TIMEZONE))
    try:
        display_manager.start()
        server_manager.start()

        if not server_manager.server_ready_event.wait(timeout=SERVER_READY_TIMEOUT):
            shared_stats['status'] = "❌ 伺服器啟動超時"
            log_manager.log("CRITICAL", f"伺服器在 {SERVER_READY_TIMEOUT} 秒內未能就緒。")
            return # 提早退出

        max_retries, retry_delay = 10, 3
        for attempt in range(max_retries):
            try:
                log_manager.log("INFO", f"正在嘗試取得代理連結... (第 {attempt + 1}/{max_retries} 次)")
                url = colab_output.eval_js(f'google.colab.kernel.proxyPort({server_manager.port})')
                if url and url.strip():
                    shared_stats['proxy_url'] = url
                    log_manager.log("SUCCESS", "✅ 成功取得代理連結！")
                    break
            except Exception as e: log_manager.log("WARN", f"嘗試取得代理連結失敗: {e}")
            if not shared_stats.get('proxy_url'):
                log_manager.log("INFO", f"將於 {retry_delay} 秒後重試...")
                time.sleep(retry_delay)

        if not shared_stats.get('proxy_url'):
            shared_stats['status'] = "❌ 取得代理連結失敗"
            log_manager.log("CRITICAL", f"在 {max_retries} 次嘗試後，仍無法取得有效的代理連結。")
            return

        # 成功取得 URL，停止儀表板刷新，顯示最終結果
        display_manager.stop()
        clear_output(wait=True)
        final_message = f"""
        <div style="border: 2px solid #4CAF50; padding: 20px; border-radius: 10px; background-color: #f0f9f0;">
            <h2 style="color: #4CAF50;">✅ 服務已成功啟動！</h2>
            <p>您的「鳳凰音訊轉錄儀」已經準備就緒。</p>
            <p>
                <strong>點擊下面的連結以開啟操作介面：</strong><br>
                <a href="{shared_stats['proxy_url']}" target="_blank" style="font-size: 1.2em; font-weight: bold; color: #1e88e5;">{shared_stats['proxy_url']}</a>
            </p>
            <p style="font-size: 0.9em; color: #555;">
                閒置超時設定為 {IDLE_TIMEOUT_SECONDS} 秒。如果沒有正在處理的任務，服務將在閒置超時後自動關閉。
            </p>
        </div>
        """
        display(HTML(final_message))
        log_manager.log("BATTLE", "=== 應用程式已上線，進入閒置監控模式 ===")

        # 進入看門狗監控迴圈
        while not server_manager._stop_event.is_set():
            time.sleep(1)
            if IDLE_TIMEOUT_SECONDS > 0:
                idle_time = time.monotonic() - shared_stats.get('last_activity_time', time.monotonic())
                if idle_time > IDLE_TIMEOUT_SECONDS:
                    log_manager.log("WARN", f"😴 系統閒置超過 {IDLE_TIMEOUT_SECONDS} 秒，將自動關閉。")
                    shared_stats['status'] = "😴 閒置超時"
                    break # 退出迴圈，進入 finally 區塊關閉

                # 更新倒數計時器供顯示
                shared_stats['idle_timeout_countdown'] = IDLE_TIMEOUT_SECONDS - idle_time

    except KeyboardInterrupt:
        log_manager.log("WARN", "🛑 偵測到使用者手動中斷...")
    except Exception as e:
        log_manager.log("CRITICAL", f"❌ 發生未預期的致命錯誤: {e}")
    finally:
        log_manager.log("INFO", "=== 任務結束，正在關閉所有服務... ===")
        if display_manager._thread.is_alive(): display_manager.stop()
        server_manager.stop()
        clear_output() # 清理最後的儀表板輸出

        # 打印最終日誌
        final_logs = []
        for log in log_manager.get_display_logs():
            ts = log['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            level = log['level']
            message = log['message']
            final_logs.append(f"[{ts}] [{level:^8}] {message}")
        print("\n".join(final_logs))

        # 歸檔日誌
        end_time = datetime.now(pytz.timezone(TIMEZONE))
        archive_reports(log_manager, start_time, end_time, shared_stats.get('status', '未知'))

        print("\n--- ✅ 所有任務完成，系統已安全關閉 ---")

if __name__ == "__main__":
    main()
