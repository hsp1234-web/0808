#@title 任務日誌報告產生器
#@markdown ---
#@markdown ### 選擇要顯示的任務狀態：
#@markdown 請勾選您想檢視的任務狀態。
show_completed = True #@param {type:"boolean"}
show_failed = True #@param {type:"boolean"}
show_processing = False #@param {type:"boolean"}
show_pending = False #@param {type:"boolean"}

#@markdown ---
#@markdown ### 設定資料庫路徑：
#@markdown 如果您在 Colab 中上傳了 `queue.db`，請確保路徑正確。
db_path_str = "db/queue.db" #@param {type:"string"}
#@markdown ---

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def format_task_log(task: sqlite3.Row) -> str:
    """將單一任務格式化為易於閱讀的純文字日誌。"""
    log_parts = []
    log_parts.append("="*80)
    log_parts.append(f"日誌時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_parts.append(f"任務 ID  : {task['task_id']}")
    log_parts.append(f"任務類型 : {task['type'].upper()}")
    log_parts.append(f"狀態     : {task['status'].upper()}")
    log_parts.append(f"建立時間 : {task['created_at']}")
    log_parts.append(f"更新時間 : {task['updated_at']}")
    log_parts.append("-"*80)

    # --- Payload 內容 ---
    payload_str = task['payload']
    if payload_str:
        try:
            payload_json = json.loads(payload_str)
            log_parts.append("▼ 任務 Payload (內容):")
            log_parts.append(json.dumps(payload_json, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            log_parts.append("▼ 任務 Payload (原始文字):")
            log_parts.append(payload_str)
    else:
        log_parts.append("▼ 任務 Payload: (無)")

    log_parts.append("-"*80)

    # --- Result 內容 ---
    result_str = task['result']
    if result_str:
        try:
            result_json = json.loads(result_str)
            log_parts.append("▼ 任務 Result (結果):")
            # 特別處理轉錄結果，使其更易讀
            if 'transcript' in result_json:
                log_parts.append("  轉錄文字:")
                log_parts.append(f"    {result_json['transcript']}")
                # 刪除已顯示的鍵，以顯示其他可能的結果欄位
                del result_json['transcript']

            if len(result_json) > 0:
                 log_parts.append("  其他結果欄位:")
                 log_parts.append(json.dumps(result_json, indent=4, ensure_ascii=False))

        except json.JSONDecodeError:
            log_parts.append("▼ 任務 Result (原始文字):")
            log_parts.append(result_str)
    else:
        log_parts.append("▼ 任務 Result: (無)")

    log_parts.append("="*80)
    return "\n".join(log_parts)

def generate_report():
    """根據使用者選擇的狀態，產生並印出日誌報告。"""
    db_path = Path(db_path_str)

    if not db_path.exists():
        print(f"❌ 錯誤：找不到資料庫檔案 '{db_path}'。")
        print("請確認您已將 `queue.db` 上傳到 Colab，並且路徑設定正確。")
        return

    selected_statuses = []
    if show_completed:
        selected_statuses.append('completed')
    if show_failed:
        selected_statuses.append('failed')
    if show_processing:
        selected_statuses.append('processing')
    if show_pending:
        selected_statuses.append('pending')

    if not selected_statuses:
        print("⚠️ 您沒有選擇任何任務狀態，因此沒有日誌可以顯示。")
        return

    print(f"正在從 '{db_path}' 讀取資料庫...")
    print(f"篩選狀態: {', '.join(selected_statuses)}")
    print("\n" + "="*40 + " 日誌報告開始 " + "="*40 + "\n")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 建立動態查詢
        query_placeholders = ','.join(['?'] * len(selected_statuses))
        sql_query = f"SELECT * FROM tasks WHERE status IN ({query_placeholders}) ORDER BY created_at DESC"

        cursor.execute(sql_query, selected_statuses)
        tasks = cursor.fetchall()

        if not tasks:
            print("ℹ️ 在指定的狀態下，找不到任何任務記錄。")
        else:
            print(f"找到了 {len(tasks)} 筆記錄。\n")
            for task in tasks:
                print(format_task_log(task))
                print("\n")

    except sqlite3.Error as e:
        print(f"❌ 讀取資料庫時發生錯誤: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
        print("="*40 + " 日誌報告結束 " + "="*40)

# 執行報告產生器
generate_report()
