# phoenix_runner.py
import subprocess
import logging
from pathlib import Path
import sys

# --- 路徑設定 ---
ROOT_DIR = Path(__file__).resolve().parent
TOOLS_DIR = ROOT_DIR / "tools"
BAKED_ENVS_DIR = ROOT_DIR / "baked_envs"

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('phoenix_runner')


class ToolExecutionError(Exception):
    """自訂錯誤類別，用於表示工具執行期間的失敗。"""
    pass


def run(tool_name: str, args: list[str], mock: bool = False) -> subprocess.Popen:
    """
    在對應的預烘烤環境中，以非同步方式執行一個工具。

    :param tool_name: 要執行的工具名稱 (例如 'transcriber')。
    :param args: 要傳遞給工具腳本的命令列參數列表。
    :param mock: 是否執行工具的模擬版本。
    :return: 一個 subprocess.Popen 物件，代表正在執行的程序。
    :raises ToolExecutionError: 如果找不到工具或其環境，或執行失敗。
    """

    effective_tool_name = f"mock_{tool_name}" if mock else tool_name
    log.info(f"🚀 請求執行工具: '{tool_name}' (實際執行: '{effective_tool_name}')")

    # 1. 驗證路徑是否存在
    tool_script_path = TOOLS_DIR / f"{effective_tool_name}.py"
    venv_python_path = BAKED_ENVS_DIR / effective_tool_name / "venv" / "bin" / "python"

    if not tool_script_path.is_file():
        msg = f"❌ 執行失敗：找不到工具腳本 {tool_script_path}"
        log.error(msg)
        raise ToolExecutionError(msg)

    if not venv_python_path.is_file():
        msg = f"❌ 執行失敗：找不到預烘烤環境的 Python 解譯器 {venv_python_path}。是否已成功執行 bake_envs.py？"
        log.error(msg)
        raise ToolExecutionError(msg)

    # 2. 構建執行命令
    command = [
        str(venv_python_path),
        str(tool_script_path)
    ] + args

    log.info(f"🔧 構建的命令: {' '.join(command)}")

    # 3. 使用 Popen 以非同步方式執行
    try:
        # 我們將 stdout 和 stderr 重新導向到檔案，以便後續偵錯
        # 這裡我們暫時先導向到 DEVNULL，保持簡單
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        log.info(f"✅ 成功啟動工具 '{effective_tool_name}'，程序 PID: {process.pid}")
        return process
    except Exception as e:
        msg = f"❌ 啟動工具 '{effective_tool_name}' 時發生未預期的錯誤: {e}"
        log.critical(msg, exc_info=True)
        raise ToolExecutionError(msg)


# --- 測試用區塊 ---
def _test_run():
    """一個簡單的測試函數，用於直接執行此腳本時進行驗證。"""
    log.info("--- Phoenix Runner 測試模式 ---")

    # 準備測試用的輸出入檔案路徑
    test_output_dir = ROOT_DIR / "temp_test_outputs"
    test_output_dir.mkdir(exist_ok=True)

    input_file = "dummy_input.wav" # 僅為示意
    output_file = test_output_dir / "mock_output.txt"

    log.info("將執行 mock_transcriber...")
    try:
        # 測試執行模擬工具
        proc = run("transcriber", args=[input_file, str(output_file)], mock=True)

        # 等待程序結束 (在真實應用中，這部分會由其他邏輯處理)
        log.info(f"等待程序 {proc.pid} 結束...")
        proc.wait(timeout=15) # 等待最多15秒

        if proc.returncode == 0:
            log.info("✅ 程序成功結束。")
            if output_file.exists():
                log.info(f"檔案已生成，內容:\n---\n{output_file.read_text(encoding='utf-8')}\n---")
            else:
                log.error("❌ 程序成功，但未找到輸出檔案！")
        else:
            log.error(f"❌ 程序以錯誤碼 {proc.returncode} 結束。")

    except ToolExecutionError as e:
        log.error(f"工具執行失敗: {e}")
    except subprocess.TimeoutExpired:
        log.error("程序執行超時！")
    finally:
        # 清理測試檔案
        # shutil.rmtree(test_output_dir)
        # log.info(f"清理測試目錄 {test_output_dir}")
        pass

if __name__ == "__main__":
    _test_run()
