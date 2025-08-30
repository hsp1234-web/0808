import sys
import subprocess
import time
import os
import re
import signal
from pathlib import Path

# --- 組態設定 ---
SERVER_READY_TIMEOUT = 120  # 根據使用者要求設定
REQUIREMENTS_FILES = [
    "requirements/server.txt",
    "requirements/transcriber.txt"
]
# 來自 colabPro.py.v18.bak 的核心指令
LAUNCH_COMMAND = ["src/core/orchestrator.py"]
# 來自 colabPro.py.v18.bak 的就緒信號
UVICORN_READY_PATTERN = re.compile(r"Uvicorn running on")

def install_dependencies():
    """安裝所有必要的 Python 依賴。"""
    print("--- 正在安裝 Python 依賴 ---")

    # 建立一個暫時的合併依賴檔案
    # 這比多次執行 pip 更好
    merged_reqs_path = Path("requirements_merged_for_startup.txt")
    with open(merged_reqs_path, "w") as outfile:
        for req_file in REQUIREMENTS_FILES:
            if Path(req_file).is_file():
                with open(req_file, "r") as infile:
                    outfile.write(infile.read())
                    outfile.write("\n")
            else:
                print(f"警告：找不到依賴檔案：{req_file}")

    # 如果 'uv' 可用，則使用它，否則使用 'pip'
    pip_command = [sys.executable, "-m", "pip", "install", "-q", "-r", str(merged_reqs_path)]
    try:
        # 檢查 'uv' 是否存在
        subprocess.check_call([sys.executable, "-m", "uv", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("偵測到 'uv'，將使用它進行更快速的安裝。")
        pip_command = [sys.executable, "-m", "uv", "pip", "install", "-q", "-r", str(merged_reqs_path)]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("未找到 'uv'，將退回使用 'pip'。")

    try:
        subprocess.check_call(pip_command)
        print("✅ 依賴安裝成功。")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依賴安裝失敗。錯誤：{e}")
        sys.exit(1)
    finally:
        # 清理合併後的檔案
        if merged_reqs_path.exists():
            merged_reqs_path.unlink()


def main():
    """
    主函式，用於安裝依賴、啟動核心伺服器，
    並在超時限制內等待其就緒。
    """
    print("--- 核心服務啟動器 ---")

    # 步驟 1: 安裝依賴
    install_dependencies()

    # 步驟 2: 啟動協調器進程
    print(f"🚀 正在啟動核心協調器: {' '.join([sys.executable] + LAUNCH_COMMAND)}")

    # 設定 PYTHONPATH 以包含 'src' 目錄，與 colabPro.py 類似
    process_env = os.environ.copy()
    src_path_str = str(Path("src").resolve())
    process_env['PYTHONPATH'] = f"{src_path_str}{os.pathsep}{process_env.get('PYTHONPATH', '')}".strip(os.pathsep)

    # 使用 preexec_fn=os.setsid 建立一個新的進程組。
    # 這允許我們稍後能殺掉整個進程樹。
    server_process = subprocess.Popen(
        [sys.executable] + LAUNCH_COMMAND,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        preexec_fn=os.setsid,
        env=process_env
    )

    print(f"協調器進程已啟動，PID: {server_process.pid}")
    print(f"正在等待伺服器就緒 (超時: {SERVER_READY_TIMEOUT} 秒)...")

    # 步驟 3: 在超時限制內等待伺服器就緒
    start_time = time.time()
    server_ready = False

    try:
        # 使用非阻塞讀取迴圈
        for line in iter(server_process.stdout.readline, ''):
            print(f"[協調器] {line.strip()}")
            if UVICORN_READY_PATTERN.search(line):
                server_ready = True
                print("\n✅ 伺服器已就緒！Uvicorn 正在運行。")
                break

            if time.time() - start_time > SERVER_READY_TIMEOUT:
                # 我們使用自訂異常來發出超時信號
                raise TimeoutError("伺服器未能在超時時間內啟動。")

        # 迴圈結束後，如果伺服器仍未就緒，表示進程已提前退出。
        if not server_ready:
            print("❌ 協調器進程在發出就緒信號前已提前退出。")

    except TimeoutError as e:
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ 監控伺服器時發生未預期錯誤: {e}")
    finally:
        # 如果伺服器已就緒，我們讓它繼續運行。
        if server_ready:
            print("\n伺服器進程現在正在背景運行。")
            print("若要停止，您可能需要手動終止該進程組。")
            # 腳本將退出，但伺服器進程會繼續運行。
        else:
            # 如果進程仍在運行（例如，超時），則終止它。
            if server_process.poll() is None:
                print("因超時或錯誤，正在終止伺服器進程...")
                try:
                    # 終止整個進程組
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                    server_process.wait(timeout=5)
                    print("伺服器進程已終止。")
                except ProcessLookupError:
                    print("進程已終止。") # 它可能在此期間已經結束
                except Exception as kill_e:
                    print(f"清理進程時發生錯誤: {kill_e}")

            print("\n--- 啟動器腳本因錯誤而結束。 ---")
            sys.exit(1)

        print("\n--- 啟動器腳本成功結束。 ---")


if __name__ == "__main__":
    main()
