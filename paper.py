#@title 任務日誌報告產生器 (v2 - 智慧搜尋版)
#@markdown ---
#@markdown ### 選擇要顯示的任務狀態：
#@markdown 請勾選您想檢視的任務狀態。
show_completed = True #@param {type:"boolean"}
show_failed = True #@param {type:"boolean"}
show_processing = False #@param {type:"boolean"}
show_pending = False #@param {type:"boolean"}

#@markdown ---
#@markdown ### (可選) 手動設定資料庫路徑：
#@markdown 一般情況下留空即可，腳本會自動搜尋。如果找到多個 `queue.db`，請將正確的路徑複製貼到此處。
db_path_str = "" #@param {type:"string"}
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
            if 'transcript' in result_json:
                log_parts.append("  轉錄文字:")
                log_parts.append(f"    {result_json['transcript']}")
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

def find_or_upload_db() -> Path | None:
    """
    智慧地尋找或引導上傳 queue.db 檔案。
    - Return: 指向資料庫檔案的 Path 物件，或在失敗時回傳 None。
    """
    # 如果使用者手動指定了路徑，優先使用
    if db_path_str:
        print(f"ℹ️ 您手動指定了路徑，將嘗試使用: '{db_path_str}'")
        path = Path(db_path_str)
        if path.is_file():
            return path
        else:
            print(f"❌ 手動指定路徑錯誤: '{db_path_str}' 不是一個有效的檔案。")
            return None

    # 自動搜尋
    print("🚀 正在自動搜尋 'queue.db' 檔案...")
    # 在 Colab 中，從 /content 開始搜尋效率更高
    search_dir = Path("/content") if Path("/content").exists() else Path("/")
    possible_paths = list(search_dir.rglob('queue.db'))

    if len(possible_paths) == 1:
        db_path = possible_paths[0]
        print(f"✅ 自動找到唯一的資料庫檔案於: {db_path}")
        return db_path
    elif len(possible_paths) > 1:
        print("⚠️ 找到多個 'queue.db' 檔案。請從下方列表中複製正確的路徑，")
        print("   並將其貼到上方的 'db_path_str' 欄位中，然後重新執行儲存格。")
        for p in possible_paths:
            print(f"  - {p}")
        return None
    else: # 找不到任何檔案，引導上傳
        print("ℹ️ 在系統中找不到 'queue.db' 檔案。")
        try:
            from google.colab import files
            print("現在將引導您上傳 `queue.db` 檔案...")
            uploaded = files.upload()
            if not uploaded:
                print("❌ 您沒有上傳任何檔案。")
                return None
            uploaded_filename = list(uploaded.keys())[0]
            db_path = Path(uploaded_filename)
            print(f"✅ 檔案 '{db_path}' 上傳成功，將使用此檔案進行分析。")
            return db_path
        except ModuleNotFoundError:
            print("❌ 錯誤：找不到資料庫檔案。如果您在本地執行，請確認檔案存在或手動指定路徑。")
            return None
        except Exception as e:
            print(f"❌ 上傳檔案時發生錯誤: {e}")
            return None

def generate_report():
    """根據使用者選擇的狀態，產生並印出日誌報告。"""
    db_path = find_or_upload_db()

    if not db_path:
        print("\n無法定位資料庫檔案，腳本終止。")
        return

    selected_statuses = []
    if show_completed: selected_statuses.append('completed')
    if show_failed: selected_statuses.append('failed')
    if show_processing: selected_statuses.append('processing')
    if show_pending: selected_statuses.append('pending')

    if not selected_statuses:
        print("⚠️ 您沒有選擇任何任務狀態，因此沒有日誌可以顯示。")
        return

    print(f"\n正在從 '{db_path}' 讀取資料庫...")
    print(f"篩選狀態: {', '.join(selected_statuses)}")
    print("\n" + "="*40 + " 日誌報告開始 " + "="*40 + "\n")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
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
