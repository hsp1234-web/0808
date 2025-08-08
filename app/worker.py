# app/worker.py
import time
from pathlib import Path
import os

# 匯入我們共享的佇列、結果儲存區和轉錄器實例
from .queue import task_queue
from . import result_store
from .core.transcriber import transcriber_instance

def run_worker():
    """
    背景工作者的主函式。
    它會持續從任務佇列中獲取任務並執行。
    """
    print("🚀 [Worker] 背景工作者已啟動，等待轉錄任務...")

    while True:
        try:
            # 從佇列中獲取任務，這是一個阻塞操作
            # 如果佇列為空，它會一直等待直到有新項目
            task_id, file_path_str = task_queue.get()
            file_path = Path(file_path_str)

            print(f"👷 [Worker] 收到新任務 (ID: {task_id})，檔案: {file_path.name}")

            # 1. 更新狀態為「處理中」
            result_store.set_status(task_id, "processing")

            # 2. 執行耗時的轉錄任務
            transcript = transcriber_instance.transcribe(file_path)

            # 3. 根據轉錄結果更新最終狀態
            if "轉錄失敗" in transcript:
                result_store.set_status(task_id, "error", result=transcript)
                print(f"❌ [Worker] 任務處理失敗 (ID: {task_id})")
            else:
                result_store.set_status(task_id, "complete", result=transcript)
                print(f"✅ [Worker] 任務處理完成 (ID: {task_id})")

        except Exception as e:
            # 全域的錯誤處理，以防萬一
            task_id_for_error = 'unknown'
            if 'task_id' in locals():
                task_id_for_error = task_id
                result_store.set_status(task_id, "error", result=f"工作者發生未預期錯誤: {e}")

            print(f"💥 [Worker] 處理任務 {task_id_for_error} 時發生致命錯誤: {e}")
            # 建議在生產環境中加入更詳細的日誌記錄

        finally:
            # 4. 清理臨時檔案
            try:
                if 'file_path' in locals() and file_path.exists():
                    os.remove(file_path)
                    print(f"🗑️ [Worker] 已刪除臨時檔案: {file_path.name}")
            except Exception as e:
                print(f"🔥 [Worker] 刪除臨時檔案 {file_path.name} 時出錯: {e}")

            # 標記任務為完成 (對於 queue.Queue 不是嚴格必要，但對於 queue.JoinableQueue 是)
            task_queue.task_done()

            # 短暫休眠，避免在極端情況下空轉CPU
            time.sleep(0.1)
