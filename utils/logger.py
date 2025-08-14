# utils/logger.py

"""
結構化日誌系統模組

提供一個設定函式 (setup_logger) 來建立一個能輸出 JSON 格式日誌的 logger。
"""

import logging
import json
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    """
    自訂的日誌格式化器，將日誌記錄轉換為 JSON 字符串。
    """
    def format(self, record: logging.LogRecord) -> str:
        """
        將 LogRecord 物件格式化為 JSON。

        Args:
            record (logging.LogRecord): logging 模組的日誌記錄物件。

        Returns:
            str: 代表該日誌的 JSON 字符串。
        """
        log_object = {
            # 精確到毫秒的時間戳 (ISO 8601 格式)
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "service_name": getattr(record, 'service_name', 'unknown_service'),
            "log_level": record.levelname,
            # 核心：從日誌記錄中提取 correlation_id，若無則為 None
            "correlation_id": getattr(record, 'correlation_id', None),
            "message": record.getMessage(),
            # 允許傳入額外的結構化數據
            "data": getattr(record, 'data', None),
        }
        return json.dumps(log_object, ensure_ascii=False)

def setup_logger(service_name: str, log_file: str) -> logging.Logger:
    """
    設定並返回一個配置好的 logger。

    Args:
        service_name (str): 產生ログ的服務名稱。
        log_file (str): 日誌輸出的目標檔案路徑。

    Returns:
        logging.Logger: 配置完成的 logger 物件。
    """
    # 移除所有現有的 handlers，避免重複記錄
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    handler = logging.FileHandler(log_file, encoding='utf-8')
    # 將服務名稱傳遞給 formatter
    formatter = JsonFormatter()
    # 將 service_name 作為一個屬性添加到所有 LogRecord 中
    # 雖然我們在 JsonFormatter 中直接讀取 record.service_name，
    # 但更穩健的方式是透過 filter 或 adapter。此處為求簡潔，
    # 我們將在 logger.info 等呼叫中傳入 service_name。
    # 不過，更簡單的方式是直接在 formatter 中處理。
    # 為了讓 formatter 能存取 service_name，我們在 logger 上設定它
    # 這不是標準做法，但很有效。一個更好的方法是使用 filter。
    # 讓我們用 filter 來做，這更乾淨。

    class ServiceNameFilter(logging.Filter):
        def filter(self, record):
            record.service_name = service_name
            return True

    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    # 清除舊的 handlers，以防重複添加
    if logger.hasHandlers():
        logger.handlers.clear()

    handler.setFormatter(formatter)
    logger.addFilter(ServiceNameFilter())
    logger.addHandler(handler)

    # 防止日誌事件傳播到 root logger
    logger.propagate = False

    return logger
