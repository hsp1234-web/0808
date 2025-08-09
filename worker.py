# worker.py
import time
import logging
import json
import subprocess
import sys
import argparse
from pathlib import Path

# 將專案根目錄加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from db import database

# --- 日誌設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger('worker')

# --- 路徑設定 ---
TOOLS_DIR = ROOT_DIR / "tools"
TRANSCRIPTS_DIR = ROOT_DIR / "transcripts"

def process_task(task: dict, use_mock: bool):
    """
    處理單一轉錄任務。

    :param task: 從資料庫獲取的任務字典。
    :param use_mock: 是否使用模擬轉錄工具。
    """
    task_id = task['task_id']
    log.info(f"🚀 開始處理任務: {task_id}")

    try:
        payload = json.loads(task['payload'])
        input_file = Path(payload['input_file'])
        model_size = payload.get('model_size', 'tiny')
        language = payload.get('language') # 可以是 None

        if not input_file.exists():
            raise FileNotFoundError(f"輸入檔案不存在: {input_file}")

        # 1. 決定要使用的工具
        tool_script_name = "mock_transcriber.py" if use_mock else "transcriber.py"
        tool_script_path = TOOLS_DIR / tool_script_name
        if not tool_script_path.exists():
             raise FileNotFoundError(f"工具腳本不存在: {tool_script_path}")

        # 2. 準備輸出路徑
        TRANSCRIPTS_DIR.mkdir(exist_ok=True)
        output_file = TRANSCRIPTS_DIR / f"{task_id}.txt"

        # 3. 構建並執行命令
        command = [
            sys.executable, # 使用與 worker 相同的 Python 解譯器
            str(tool_script_path),
            str(input_file),
            str(output_file),
            f"--model_size={model_size}"
        ]
        if language:
            command.append(f"--language={language}")

        log.info(f"🔧 執行命令: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

        # 4. 處理執行結果
        if result.returncode == 0:
            log.info(f"✅ 工具成功執行任務: {task_id}")
            # 讀取轉錄結果
            transcript = output_file.read_text(encoding='utf-8').strip()
            # 將結果以 JSON 格式儲存
            final_result = json.dumps({
                "transcript": transcript,
                "tool_stdout": result.stdout,
            })
            database.update_task_status(task_id, 'completed', final_result)
        else:
            log.error(f"❌ 工具執行任務失敗: {task_id}。返回碼: {result.returncode}")
            error_message = result.stderr or result.stdout or "未知錯誤"
            final_result = json.dumps({
                "error": error_message,
                "tool_stdout": result.stdout,
                "tool_stderr": result.stderr
            })
            database.update_task_status(task_id, 'failed', final_result)

    except Exception as e:
        log.critical(f"💥 處理任務 {task_id} 時發生未預期的嚴重錯誤: {e}", exc_info=True)
        database.update_task_status(task_id, 'failed', json.dumps({"error": str(e)}))


def main_loop(use_mock: bool, poll_interval: int):
    """
    工人的主迴圈，持續從佇列中拉取並處理任務。
    """
    log.info(f"🤖 Worker 已啟動。模式: {'模擬 (Mock)' if use_mock else '真實 (Real)'}。查詢間隔: {poll_interval} 秒。")
    try:
        while True:
            task = database.fetch_and_lock_task()
            if task:
                process_task(task, use_mock)
            else:
                # 佇列為空，稍作等待
                time.sleep(poll_interval)
    except KeyboardInterrupt:
        log.info("🛑 收到中斷信號，Worker 正在關閉...")
    except Exception as e:
        log.critical(f"🔥 Worker 主迴圈發生致命錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="背景工作處理器。")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="如果設置此旗標，則使用 mock_transcriber.py 進行測試。"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="當佇列為空時，輪詢資料庫的間隔時間（秒）。"
    )
    args = parser.parse_args()

    # 在啟動主迴圈之前，先確保資料庫已初始化
    database.initialize_database()

    main_loop(args.mock, args.poll_interval)
