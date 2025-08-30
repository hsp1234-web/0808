# -*- coding: utf-8 -*-
#@title 📥🐺 善狼一鍵啟動器 (v19.1-async-refactored) 🐺
#@markdown ---
#@markdown ### **(1) 專案來源設定**
#@markdown > **請提供 Git 倉庫的網址、要下載的分支或標籤，以及本地資料夾名稱。**
#@markdown ---
#@markdown **後端程式碼倉庫 (REPOSITORY_URL)**
REPOSITORY_URL = "https://github.com/hsp1234-web/0808.git" #@param {type:"string"}
#@markdown **後端版本分支或標籤 (TARGET_BRANCH_OR_TAG)**
TARGET_BRANCH_OR_TAG = "838" #@param {type:"string"}
#@markdown **專案資料夾名稱 (PROJECT_FOLDER_NAME)**
PROJECT_FOLDER_NAME = "wolf_project" #@param {type:"string"}
#@markdown **強制刷新後端程式碼 (FORCE_REPO_REFRESH)**
#@markdown > **如果勾選，每次執行都會先刪除舊的專案資料夾，再重新下載。**
FORCE_REPO_REFRESH = True #@param {type:"boolean"}
#@markdown > **v16 架構更新：舊的依賴包 (`dependencies.tar.gz`) 已被廢棄，此選項不再有效。**
FORCE_DEPS_REFRESH = False #@param {type:"boolean"}
#@markdown **輕量測試模式 (LIGHT_MODE)**
#@markdown > **勾選後，將以輕量模式啟動，使用 `tiny.en` 模型並安裝較少的依賴，適合快速測試。**
LIGHT_MODE = True #@param {type:"boolean"}
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
# 版本: 19.1 (架構: asyncio-refactored)
# 日期: 2025-08-30
#
# 本次變更重點:
# 1. **結構優化**: 將輔助函式 (tunnels, installer) 從主函式中移出，
#    變為模組級別的函式，以利於未來的單元測試和 mock。
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
import re
from pathlib import Path
import traceback
from datetime import datetime
from collections import deque
import html
import asyncio

# --- 異步依賴 ---
try:
    import aiohttp
except ImportError:
    print("正在安裝 aiohttp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "aiohttp"])
    import aiohttp

# --- Colab 環境兼容性修復 ---
try:
    import nest_asyncio
except ImportError:
    print("正在安裝 nest_asyncio 以相容 Colab 環境...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "nest_asyncio"])
    import nest_asyncio
nest_asyncio.apply()

# --- 模擬 Colab 環境 ---
try:
    from google.colab import output as colab_output
    from IPython.display import display, HTML, clear_output as ipy_clear_output
    import pytz
    IN_COLAB = True
except ImportError:
    class MockColab:
        def eval_js(self, *args, **kwargs): return ""
        def clear_output(self, wait=False): print("\n--- 清除輸出 ---\n")
        def display(self, *args, **kwargs): pass
        def HTML(self, *args, **kwargs): pass
    colab_output = MockColab().eval_js
    ipy_clear_output = MockColab().clear_output
    display = MockColab().display
    HTML = MockColab().HTML
    class MockPytz:
        def timezone(self, tz_str): from datetime import timezone, timedelta; return timezone(timedelta(hours=8))
    pytz = MockPytz()
    IN_COLAB = False
    print("警告：未在 Colab 環境中執行，將使用模擬的 display 功能。")


# ==============================================================================
# PART 1: UI 與日誌管理器 (邏輯保留)
# ==============================================================================

ANSI_COLORS = {"SUCCESS": "\033[32m", "WARN": "\033[33m", "ERROR": "\033[31m", "CRITICAL": "\033[31m", "RESET": "\033[0m", "INFO": "\033[34m", "RUNNER": "\033[90m"}
def colorize(text, level): return f"{ANSI_COLORS.get(level, '')}{text}{ANSI_COLORS.get('RESET', '')}"

class DisplayManager:
    def __init__(self, shared_state): self._state = shared_state; self._log_deque = deque(maxlen=LOG_DISPLAY_LINES); self._full_history = []
    def log(self, level, message):
        now = datetime.now(pytz.timezone(TIMEZONE))
        for line in str(message).split('\n'): self._log_deque.append({"timestamp": now, "level": level.upper(), "message": line}); self._full_history.append(f"[{now.isoformat()}] [{level.upper():^8}] {line}")
    def get_full_log_history(self): return self._full_history
    def print_ui(self):
        if ENABLE_CLEAR_OUTPUT: ipy_clear_output(wait=True)
        output = ["🚀 善狼一鍵啟動器 v19.1-async-refactored 🚀", ""]
        for log_item in self._log_deque: output.append(f"[{log_item['timestamp'].strftime('%H:%M:%S')}] {colorize(f'[{log_item['level']:^8}]', log_item['level'])} {log_item['message']}")
        try: import psutil; cpu, ram = f"{psutil.cpu_percent():5.1f}%", f"{psutil.virtual_memory().percent:5.1f}%"
        except ImportError: cpu, ram = " N/A ", " N/A "
        elapsed = time.monotonic() - self._state.get("start_time_monotonic", time.monotonic()); mins, secs = divmod(elapsed, 60)
        status = self._state.get("status", "初始化...")
        output.extend(["", f"⏱️ {int(mins):02d}分{int(secs):02d}秒 | 💻 CPU: {cpu} | 🧠 RAM: {ram} | 🔥 狀態: {status}", "\n🔗 公開存取網址:"])
        urls = self._state.get("urls", {})
        if not urls and status not in ["✅ 應用程式已就緒", "❌ 啟動失敗"]: output.append("  - (正在產生...)")
        else:
            for name in ["Cloudflare", "Localtunnel", "Colab"]:
                url_info = urls.get(name)
                if url_info:
                    url, password, error = url_info.get("url"), url_info.get("password"), url_info.get("error")
                    if error: output.append(f"  - {name+':':<15} ❌ {error}")
                    else: output.append(f"  - {name+':':<15} {url}");_ = password and output.append(f"    {'密碼:':<15} {password}")
        print("\n".join(output), flush=True)

def create_log_viewer_html(log_manager):
    # ... (Implementation unchanged)
    pass

# ==============================================================================
# PART 2: 核心啟動邏輯 (Asyncio Refactored)
# ==============================================================================

# --- Synchronous setup functions ---
def download_repository(log_manager):
    # ... (Implementation unchanged)
    pass
def _install_if_needed(requirements_path: Path, log_manager: DisplayManager, prefix: str = ""):
    # ... (Implementation unchanged)
    pass

# --- New Async Helper Functions (moved to module level for testability) ---
async def _run_command_async(command):
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0: raise RuntimeError(f"Command {' '.join(command)} failed: {stderr.decode()}")
    return stdout.decode()

async def _run_tunnel_service(shared_state, log_manager, name, command, pattern, cwd):
    # ... (Implementation unchanged)
    pass
async def _get_colab_url(shared_state, log_manager, port):
    # ... (Implementation unchanged)
    pass
async def find_port_in_stream(stream, log_manager, shared_state):
    # ... (Implementation unchanged)
    pass
async def _background_dependency_installer(project_path: Path, log_manager, shared_state):
    # ... (Implementation unchanged)
    pass

async def main_async():
    shared_state = {"start_time_monotonic": time.monotonic(), "status": "初始化...", "urls": {}, "subprocesses": [], "url_queue": asyncio.Queue()}
    log_manager = DisplayManager(shared_state)
    orchestrator_proc = None
    background_tasks = []

    async def ui_refresh_task():
        while True:
            try: log_manager.print_ui(); await asyncio.sleep(UI_REFRESH_SECONDS)
            except asyncio.CancelledError: break

    ui_task = asyncio.create_task(ui_refresh_task())

    try:
        project_path_str = download_repository(log_manager)
        if not project_path_str: raise RuntimeError("專案下載失敗")
        project_path = Path(project_path_str)
        _install_if_needed(project_path / "requirements" / "server.txt", log_manager, prefix="[主]")

        shared_state["status"] = "正在啟動後端服務..."; manager_env = os.environ.copy()
        if LIGHT_MODE: manager_env["LIGHT_MODE"] = "1"
        src_path_str = str((project_path / "src").resolve()); manager_env['PYTHONPATH'] = f"{src_path_str}{os.pathsep}{manager_env.get('PYTHONPATH', '')}".strip(os.pathsep)

        command = [sys.executable, str(project_path / "src" / "core" / "orchestrator.py"), "--no-mock"]
        orchestrator_proc = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=manager_env, cwd=project_path)
        shared_state['subprocesses'].append(orchestrator_proc)

        app_port = await asyncio.wait_for(find_port_in_stream(orchestrator_proc.stdout, log_manager, shared_state), timeout=30)
        if app_port is None: raise RuntimeError("後端服務日誌流結束，但未找到埠號信號。")

        tunnel_tasks = []
        if ENABLE_CLOUDFLARE:
             cf_path = project_path / 'cloudflared'
             if not cf_path.exists():
                log_manager.log("INFO", "下載 Cloudflared..."); await _run_command_async(['wget', '-q', 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', '-O', str(cf_path)])
                await _run_command_async(['chmod', '+x', str(cf_path)])
             tunnel_tasks.append(_run_tunnel_service(shared_state, log_manager, "Cloudflare", [str(cf_path), 'tunnel', '--url', f'http://127.0.0.1:{app_port}'], r'(https?://\S+\.trycloudflare\.com)', project_path))
        if ENABLE_LOCALTUNNEL: tunnel_tasks.append(_run_tunnel_service(shared_state, log_manager, "Localtunnel", ['npx', 'localtunnel', '--port', str(app_port), '--bypass-tunnel-reminder'], r'(https?://\S+\.loca\.lt)', project_path))
        if ENABLE_COLAB_PROXY: tunnel_tasks.append(_get_colab_url(shared_state, log_manager, app_port))

        if tunnel_tasks:
            asyncio.gather(*tunnel_tasks)
            shared_state["status"] = "正在驗證服務健康度..."; health_check_passed = False
            try:
                async with asyncio.timeout(30):
                    while not health_check_passed:
                        url_to_test = await shared_state["url_queue"].get()
                        async with aiohttp.ClientSession() as session:
                            try:
                                async with session.get(f"{url_to_test}/api/health", timeout=10) as response:
                                    if response.status == 200 and (await response.json()).get("status") == "ok":
                                        log_manager.log("SUCCESS", f"✅ 健康檢查通過: {url_to_test}"); shared_state["status"] = "✅ 應用程式已就緒"; health_check_passed = True; break
                            except Exception: log_manager.log("WARN", f"健康檢查失敗: {url_to_test}，嘗試下一個...")
            except TimeoutError:
                 if not health_check_passed: raise RuntimeError("所有通道都無法在30秒內通過健康檢查")
        else:
            shared_state["status"] = "✅ 應用程式已就緒 (無公開通道)"

        background_tasks.append(asyncio.create_task(_background_dependency_installer(project_path, log_manager, shared_state)))
        log_manager.log("INFO", "啟動器將保持運行..."); await orchestrator_proc.wait()

    except Exception as e:
        shared_state["status"] = "❌ 啟動失敗"; log_manager.log("CRITICAL", f"啟動器發生致命錯誤: {e}")
    finally:
        ui_task.cancel()
        for task in background_tasks: task.cancel()
        for proc in shared_state["subprocesses"]:
            if proc.returncode is None:
                try: proc.terminate()
                except ProcessLookupError: pass
        await asyncio.gather(*[p.wait() for p in shared_state["subprocesses"] if p.returncode is None], return_exceptions=True)
        log_manager.log("INFO", "--- 啟動器執行結束 ---"); log_manager.print_ui()
        display(HTML(create_log_viewer_html(log_manager)))

# ==============================================================================
# FINAL EXECUTION BLOCK
# ==============================================================================
if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n🛑 操作已被使用者手動中斷。")
    except Exception as e:
        print(f"\n❌ 啟動器發生頂層錯誤: {e}"); traceback.print_exc()
