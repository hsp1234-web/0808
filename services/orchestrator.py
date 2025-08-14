# services/orchestrator.py

"""
業務流程編排模組 (Orchestrator)

負責協調一個或多個工作者 (Worker) 來完成一項複雜的任務。
它負責接收從 API 伺服器傳來的請求，並將其分派給合適的工作者。
"""

from . import worker
from utils.logger import setup_logger

# 設定此服務的專屬 logger
SERVICE_NAME = "orchestrator"
logger = setup_logger(SERVICE_NAME, "logs/backend.log")

def process_task(task_data: dict, correlation_id: str):
    """
    編排一項任務，可能會呼叫多個工作者。

    Args:
        task_data (dict): 任務相關的數據。
        correlation_id (str): 用於追蹤此任務的唯一 ID。
    """
    log_extra = {"correlation_id": correlation_id}
    logger.info("開始編排任務", extra=log_extra)

    # 在此範例中，我們直接呼叫一個工作者
    try:
        worker.perform_work({**task_data, "orchestrator_processed": True}, correlation_id)
        logger.info("任務編排成功", extra=log_extra)
    except Exception as e:
        logger.error(f"任務編排失敗: {e}", extra=log_extra, exc_info=True)
        # 根據需要，可以選擇重新引發異常或進行其他錯誤處理
        raise
