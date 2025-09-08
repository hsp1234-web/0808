# -*- coding: utf-8 -*-
import logging
import sys
from datetime import datetime
import pytz

# 定義 POC 專用的日誌檔案名稱
LOG_FILE = "poc.log"
# 定義時區
TIMEZONE = pytz.timezone('Asia/Taipei')

class TaipeiFormatter(logging.Formatter):
    """
    自訂日誌格式化器，將時間戳轉換為台北時區。
    """
    def converter(self, timestamp):
        dt = datetime.fromtimestamp(timestamp)
        return TIMEZONE.localize(dt)

    def formatTime(self, record, datefmt=None):
        dt = self.converter(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3] + f" {dt.tzname()}"
        return s

def get_poc_logger(name: str):
    """
    獲取並設定一個 POC 專用的 logger。

    Args:
        name (str): Logger 的名稱，通常是模組的 __name__。

    Returns:
        logging.Logger: 已設定好的 Logger 物件。
    """
    logger = logging.getLogger(name)

    # 防止重複添加 handler
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    # 建立檔案 handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # 建立控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 建立日誌格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = TaipeiFormatter(log_format)

    # 設定格式
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加 handler 到 logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

if __name__ == '__main__':
    # 測試 logger 是否正常運作
    logger = get_poc_logger(__name__)
    logger.info("這是一條測試日誌訊息，確認時區設定是否正確。")

    # 驗證日誌檔案是否被建立
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            print(f"\n--- 日誌檔案 '{LOG_FILE}' 內容 ---")
            print(f.read())
            print("---------------------------------")
    except FileNotFoundError:
        print(f"錯誤：日誌檔案 '{LOG_FILE}' 未被建立。")
