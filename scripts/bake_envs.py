# scripts/bake_envs.py
import sys
import subprocess
import ast
import logging
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

# --- 設定 ---
ROOT_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT_DIR / "tools"
BAKED_ENVS_DIR = ROOT_DIR / "baked_envs"

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('env_baker')

def run_command(command: list[str], cwd: Path):
    """執行一個子程序命令並記錄其輸出。"""
    log.info(f"🏃 執行命令: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            encoding='utf-8'
        )
        if process.stdout:
            log.info(f"STDOUT:\n{process.stdout}")
        if process.stderr:
            log.warning(f"STDERR:\n{process.stderr}")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"❌ 命令執行失敗: {' '.join(command)}")
        log.error(f"返回碼: {e.returncode}")
        log.error(f"STDOUT:\n{e.stdout}")
        log.error(f"STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError as e:
        log.error(f"❌ 命令執行失敗: {e.strerror} - '{e.filename}'")
        return False

def get_tool_dependencies(tool_path: Path) -> dict:
    """安全地從 Python 原始碼檔案中解析 'DEPENDENCIES' 字典。"""
    log.info(f"正在解析 '{tool_path.name}' 的依賴...")
    try:
        with open(tool_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                if isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'DEPENDENCIES':
                    dependencies = ast.literal_eval(node.value)
                    if isinstance(dependencies, dict):
                        dep_list = list(dependencies.values())
                        log.info(f"✅ 在 '{tool_path.name}' 中找到依賴: {dep_list if dep_list else '無'}")
                        return dependencies

        log.warning(f"⚠️ 在 '{tool_path.name}' 中未找到 'DEPENDENCIES' 字典，視為無依賴。")
        return {}
    except Exception as e:
        log.error(f"❌ 解析 '{tool_path.name}' 時發生錯誤: {e}", exc_info=True)
        return {}

def bake_environment(tool_path: Path) -> bool:
    """為單一工具執行完整的烘烤流程（無壓縮）。"""
    tool_name = tool_path.stem
    log.info(f"--- 開始為 '{tool_name}' 準備環境 ---")

    dependencies = get_tool_dependencies(tool_path)
    # 如果沒有依賴，我們仍然需要為它建立一個空的 venv，以保持 runner 邏輯的一致性

    venv_dir = BAKED_ENVS_DIR / tool_name / "venv"

    try:
        if venv_dir.exists():
            log.warning(f"發現舊的環境，正在清理: {venv_dir}")
            shutil.rmtree(venv_dir)

        # 1. 使用 uv 建立虛擬環境
        log.info(f"⚙️  正在建立虛擬環境: {venv_dir}")
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        # 使用當前執行的 python 版本來建立 venv
        uv_command = ["uv", "venv", str(venv_dir), "--python", sys.executable]
        if not run_command(uv_command, cwd=ROOT_DIR):
            return False

        # 2. 安裝依賴 (如果有的話)
        deps_to_install = list(dependencies.values())
        if not deps_to_install:
            log.info(f"'{tool_name}' 沒有依賴需要安裝。")
        else:
            log.info(f"📦 正在為 '{tool_name}' 安裝 {len(deps_to_install)} 個依賴...")
            python_executable = venv_dir / "bin" / "python"
            install_command = ["uv", "pip", "install", f"--python={python_executable}"] + deps_to_install
            if not run_command(install_command, cwd=ROOT_DIR):
                return False

        log.info(f"🎉 成功為 '{tool_name}' 準備好環境！")
        return True

    except Exception as e:
        log.error(f"❌ 在為 '{tool_name}' 準備環境時發生未預期的錯誤: {e}", exc_info=True)
        return False

def main():
    """主函數，執行所有工具的環境烘烤。"""
    log.info("🔥 環境烘烤器啟動 (AST探索, 平行處理, 無壓縮模式) 🔥")

    BAKED_ENVS_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"烘烤後的環境將存放於: {BAKED_ENVS_DIR}")

    tool_files = [p for p in TOOLS_DIR.glob("*.py") if p.is_file() and not p.name.startswith('_')]
    if not tool_files:
        log.warning("在 'tools/' 目錄下未找到任何工具腳本。")
        return

    log.info(f"找到 {len(tool_files)} 個工具需要處理: {[t.name for t in tool_files]}")

    # 在此環境中，平行處理可能不是必須的，但這是更穩健的設計
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(bake_environment, tool_files))

    success_count = sum(1 for r in results if r)
    failure_count = len(tool_files) - success_count

    log.info("--- 烘烤流程總結 ---")
    log.info(f"✅ 成功: {success_count} 個")
    if failure_count > 0:
        log.error(f"❌ 失敗: {failure_count} 個")
        sys.exit(1)
    else:
        log.info("🎉 所有環境均已成功準備！")

if __name__ == "__main__":
    main()
