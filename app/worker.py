# app/worker.py
import time
from pathlib import Path
import os
import queue
import logging

# 匯入我們共享的佇列、結果儲存區、以及新的狀態管理器
from .queue import task_queue
from . import result_store
from .state import update_worker_status
# 現在我們可以安全地匯入單例，它會根據環境變數自動成為真實的或模擬的實例
from .core.transcriber import transcriber_instance

# 為此模組建立一個專用的 logger
log = logging.getLogger('worker')

def run_worker():
    """
    背景工作者的主函式。
    它會持續從任務佇列中獲取任務、執行，並透過共享狀態模組回報其狀態。
    """
    # For clarity, we'll assign the global instance to a local variable.
    # This instance will be either a real or a mock transcriber based on the env var.
    transcriber = transcriber_instance

    if os.environ.get("MOCK_TRANSCRIBER") == "true":
        log.warning("⚠️ 警告：工作者正在以「模擬模式」運行！將不會執行任何真實的 AI 推理。")

    log.info("背景工作者已啟動，準備與監控核心同步...")
    update_worker_status('idle') # 初始狀態為閒置

    while True:
        try:
            task_id, file_path_str, model_size, language = task_queue.get(timeout=1)

            update_worker_status('busy')
            log.warning(f"🚚 收到新任務 (ID: {task_id})，進入忙碌狀態。")
            file_path = Path(file_path_str)

            try:
                # 定義一個回呼函式，用於從轉錄器接收進度更新
                def status_updater(detail_message: str):
                    log.info(f"進度更新 (ID: {task_id}): {detail_message}")
                    result_store.set_status(task_id, "processing", detail=detail_message)

                # 1. 更新任務狀態為「處理中」，並傳入第一個狀態
                status_updater("任務準備中...")

                # 2. 執行耗時的轉錄任務，並傳入回呼函式
                log.info(f"🚧 [PID:{os.getpid()}] 即將呼叫核心轉錄函式 (transcriber.transcribe)...")
                transcript = transcriber.transcribe(
                    audio_path=file_path,
                    model_size=model_size,
                    language=language,
                    status_callback=status_updater
                )
                log.info(f"🎉 [PID:{os.getpid()}] 核心轉錄函式已成功返回。")

                # 3. 根據轉錄結果更新最終狀態
                if "轉錄失敗" in transcript:
                    result_store.set_status(task_id, "error", result=transcript)
                    log.error(f"❌ 任務處理失敗 (ID: {task_id})")
                else:
                    result_store.set_status(task_id, "complete", result=transcript)
                    log.warning(f"✅ 任務處理完成 (ID: {task_id})")

            except Exception as e:
                # 處理任務時的內部錯誤
                log.critical(f"處理任務 {task_id} 時發生致命錯誤: {e}", exc_info=True)
                if 'task_id' in locals():
                    result_store.set_status(task_id, "error", result=f"工作者發生未預期錯誤: {e}")

            finally:
                # 4. 清理臨時檔案
                try:
                    if 'file_path' in locals() and file_path.exists():
                        os.remove(file_path)
                        log.info(f"已刪除臨時檔案: {file_path.name}")
                except Exception as e:
                    log.error(f"刪除臨時檔案 {file_path.name} 時出錯: {e}")

                # 標記任務為完成
                task_queue.task_done()

                # 任務結束，切換回閒置狀態，準備接收下一個任務
                log.warning(f"🔄 任務 {task_id} 流程結束，返回待命狀態。")
                update_worker_status('idle')

        except queue.Empty:
            # --- 閒置路徑 ---
            # 佇列為空，表示工作者目前閒置。更新狀態並發送心跳。
            update_worker_status('idle')
            log.debug("... 待命中，心跳...")
            # 迴圈將繼續，1秒後再次檢查佇列
            continue

        except Exception as e:
            # --- 全域錯誤路徑 ---
            log.critical(f"發生了非預期的全域錯誤: {e}", exc_info=True)
            update_worker_status('idle') # 嘗試恢復到閒置狀態
            time.sleep(1) # 短暫休眠以避免快速的錯誤迴圈
