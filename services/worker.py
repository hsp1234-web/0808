# services/worker.py

"""
工作者模組 (Worker)

負責執行具體的、單一的業務邏輯。
這是請求處理鏈路的最終執行單元。
"""

from utils.logger import setup_logger
import time

# 設定此服務的專屬 logger
SERVICE_NAME = "worker"
logger = setup_logger(SERVICE_NAME, "logs/backend.log")

def perform_work(work_data: dict, correlation_id: str):
    """
    執行具體的業務操作。

    Args:
        work_data (dict): 執行工作所需的具體數據。
        correlation_id (str): 用於追蹤此操作的唯一 ID。
    """
    log_extra = {
        "correlation_id": correlation_id,
        "data": {"work_data": work_data}
    }
    logger.info("Worker 開始執行具體工作", extra=log_extra)

    # 模擬實際工作延遲
    time.sleep(0.5)

    # 可以在這裡加入可能失敗的邏輯
    if work_data.get("should_fail", False):
        logger.warning("偵測到潛在問題，工作可能無法成功完成。", extra=log_extra)
        raise ValueError("模擬一個在 Worker 中發生的錯誤")

    logger.info("工作處理完成", extra=log_extra)
