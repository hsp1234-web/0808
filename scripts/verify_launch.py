# scripts/verify_launch.py
import sys
import subprocess
import pathlib
import shutil
import time
import os

# --- 組態設定 ---
# 專案倉庫的根目錄
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
# 用於驗證的臨時資料夾名稱
VERIFY_DIR_NAME = "verification_env"
# 伺服器啟動的超時時間 (秒)
SERVER_TIMEOUT = 120  # 增加超時以應對較慢的依賴安裝
# --- 組態設定結束 ---

def log(message):
    """簡易日誌記錄器"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] [VERIFY] {message}")

def run_command(command, cwd, venv_python=None):
    """執行一個命令並即時串流其輸出"""
    executable = command[0]
    if venv_python:
        # 如果指定了 venv 的 python，就用它來執行命令
        # 例如，將 `pip install` 轉換為 `/path/to/venv/bin/python -m pip install`
        if executable == "pip":
            command = [str(venv_python), "-m"] + command
        elif executable == "python":
             command = [str(venv_python)] + command[1:]

    log(f"正在執行命令: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        bufsize=1 # Line-buffered
    )

    for line in iter(process.stdout.readline, ''):
        print(f"    | {line.strip()}")

    process.wait()
    if process.returncode != 0:
        log(f"❌ 命令失敗，返回碼 {process.returncode}")
        raise RuntimeError(f"命令執行失敗: {' '.join(command)}")
    log("✅ 命令成功。")


def main():
    """主驗證函式"""
    verify_dir = PROJECT_ROOT / VERIFY_DIR_NAME
    server_process = None

    # --- 如果需要，從先前的執行中清理 ---
    if verify_dir.exists():
        log(f"偵測到已存在的驗證目錄，正在刪除: {verify_dir}")
        shutil.rmtree(verify_dir)

    try:
        # --- 1. 設定驗證環境 ---
        log(f"正在建立臨時驗證目錄於: {verify_dir}")
        verify_dir.mkdir()

        log(f"正在從 {PROJECT_ROOT} 複製專案檔案至 {verify_dir}")
        shutil.copytree(
            PROJECT_ROOT,
            verify_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(VERIFY_DIR_NAME, '.git', '__pycache__', '*.pyc', '.*')
        )

        # --- 2. 建立虛擬環境 ---
        log("正在建立 Python 虛擬環境...")
        venv_dir = verify_dir / ".venv"
        run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=verify_dir)

        # 根據作業系統決定 python 可執行檔路徑
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
        else:
            venv_python = venv_dir / "bin" / "python"

        log(f"虛擬環境已建立。Python 可執行檔: {venv_python}")

        # --- 3. 安裝依賴 ---
        log("正在從 requirements.txt 安裝依賴...")
        requirements_path = verify_dir / "requirements.txt"
        if not requirements_path.exists():
            raise FileNotFoundError("在專案根目錄中找不到 requirements.txt！")

        run_command(["pip", "install", "-r", str(requirements_path)], cwd=verify_dir, venv_python=venv_python)

        # --- 4. 啟動伺服器並驗證 ---
        log("正在嘗試啟動伺服器...")
        launch_script_path = verify_dir / "scripts" / "launch.py"

        server_process = subprocess.Popen(
            [str(venv_python), str(launch_script_path), "--port", "8888"],
            cwd=verify_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1
        )

        log(f"伺服器進程已啟動 (PID: {server_process.pid})。正在等待 'Uvicorn running on' 訊息...")

        start_time = time.time()
        server_ready = False

        while time.time() - start_time < SERVER_TIMEOUT:
            if server_process.poll() is not None:
                log("❌ 伺服器進程在就緒前意外終止。")
                break

            line = server_process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue

            print(f"    | {line.strip()}")
            if "Uvicorn running on" in line:
                log("✅ 伺服器已就緒！驗證成功。")
                server_ready = True
                break

        if not server_ready:
            if server_process.poll() is None:
                log(f"❌ 超時！伺服器在 {SERVER_TIMEOUT} 秒內未能就緒。")
            # 讀取剩餘輸出以供除錯
            for line in server_process.stdout:
                 print(f"    | {line.strip()}")
            raise RuntimeError("伺服器驗證失敗。")

    except Exception as e:
        log(f"驗證過程中發生錯誤: {e}")
        sys.exit(1)
    finally:
        # --- 5. 清理 ---
        log("開始清理...")
        if server_process and server_process.poll() is None:
            log(f"正在終止伺服器進程 (PID: {server_process.pid})...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                log("伺服器進程未能正常終止，已強制結束。")

        if verify_dir.exists():
            log(f"正在刪除驗證目錄: {verify_dir}")
            shutil.rmtree(verify_dir)
        log("清理完成。")


if __name__ == "__main__":
    main()
