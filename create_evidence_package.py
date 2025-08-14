# create_evidence_package.py

"""
數位證據包生成工具

此腳本用於從集中的日誌檔案中，根據指定的 correlation_id，
提取所有相關的日誌記錄，並將其打包成一個獨立的 JSON 檔案。
"""

import argparse
import json
import os

LOG_FILE_PATH = "logs/backend.log"
OUTPUT_DIR = "evidence_packages"

def create_evidence_package(correlation_id: str):
    """
    根據 correlation_id 搜尋日誌並創建證據包。

    Args:
        correlation_id (str): 要搜尋的追蹤 ID。
    """
    print(f"開始搜尋 Correlation ID 為 '{correlation_id}' 的日誌...")

    if not os.path.exists(LOG_FILE_PATH):
        print(f"錯誤：日誌檔案 '{LOG_FILE_PATH}' 不存在。請先運行模擬程序以產生日誌。")
        return

    related_logs = []
    try:
        with open(LOG_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    if log_entry.get("correlation_id") == correlation_id:
                        related_logs.append(log_entry)
                except json.JSONDecodeError:
                    # 忽略無法解析的行
                    print(f"警告：發現無法解析的日誌行，已跳過: {line.strip()}")
                    continue
    except IOError as e:
        print(f"錯誤：讀取日誌檔案時發生錯誤: {e}")
        return

    if not related_logs:
        print(f"找不到任何與 Correlation ID '{correlation_id}' 相關的日誌。")
        return

    # 確保輸出目錄存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_filename = f"evidence_{correlation_id}.json"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            # 使用 indent 使 JSON 檔案更具可讀性
            json.dump(related_logs, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"錯誤：寫入證據包檔案時發生錯誤: {e}")
        return

    print(f"\n成功創建數位證據包！")
    print(f"共找到 {len(related_logs)} 條相關日誌。")
    print(f"檔案已儲存至: {output_filepath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="從日誌檔案中為指定的 Correlation ID 創建一個數位證據包。",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "correlation_id",
        type=str,
        help="要提取日誌的唯一 Correlation ID。"
    )
    args = parser.parse_args()

    create_evidence_package(args.correlation_id)
