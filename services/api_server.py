# services/api_server.py

"""
API 伺服器模組

負責接收外部請求，並作為請求處理鏈路的起點。
它會為每一個新的請求生成一個唯一的 `correlation_id`。
"""

import uuid
from . import orchestrator
from utils.logger import setup_logger

# 設定此服務的專屬 logger
SERVICE_NAME = "api_server"
logger = setup_logger(SERVICE_NAME, "logs/backend.log")

def handle_request(request_data: dict):
    """
    處理單一外部請求的進入點。

    Args:
        request_data (dict): 來自外部請求的數據。
    """
    # 為這次請求生成一個全域唯一的追蹤 ID
    correlation_id = str(uuid.uuid4())

    # 使用結構化日誌記錄事件
    log_extra = {
        "correlation_id": correlation_id,
        "data": {"request_body": request_data}
    }
    logger.info("接收到新請求", extra=log_extra)

    # 將請求與追蹤 ID 傳遞給下一個服務
    orchestrator.process_task(request_data, correlation_id)
