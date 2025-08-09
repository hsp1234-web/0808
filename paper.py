#@title 整合式日誌報告產生器 (v3)
#@markdown ---
#@markdown ### 報告選項
#@markdown 勾選以顯示對應的報告區塊。
顯示任務報告 = True #@param {type:"boolean"}
顯示系統日誌 = True #@param {type:"boolean"}

#@markdown ---
#@markdown ### (A) 任務報告篩選
#@markdown 選擇要顯示的 **任務最終狀態**。
顯示已完成 = True #@param {type:"boolean"}
顯示已失敗 = True #@param {type:"boolean"}
顯示處理中 = False #@param {type:"boolean"}
顯示待處理 = False #@param {type:"boolean"}

#@markdown ---
#@markdown ### (B) 系統日誌篩選
#@markdown 選擇要顯示的 **日誌來源** 和 **日誌等級**。
#@markdown **來源:**
顯示_Orchestrator = True #@param {type:"boolean"}
顯示_Worker = True #@param {type:"boolean"}
顯示_API_Server = True #@param {type:"boolean"}
#@markdown **等級:**
顯示_INFO = True #@param {type:"boolean"}
顯示_WARNING = True #@param {type:"boolean"}
顯示_ERROR = True #@param {type:"boolean"}
顯示_CRITICAL = True #@param {type:"boolean"}


#@markdown ---
#@markdown ### (可選) 手動設定資料庫路徑
#@markdown 一般情況下留空即可，腳本會自動搜尋。如果找到多個 `queue.db`，請將正確的路徑複製貼到此處。
db_path_str = "" #@param {type:"string"}
#@markdown ---

import sqlite3
import json
from pathlib import Path
from datetime import datetime
import sys

# --- 核心功能 ---

def find_or_upload_db() -> Path | None:
    """智慧地尋找或引導上傳 queue.db 檔案。"""
    if db_path_str:
        print(f"ℹ️ 您手動指定了路徑，將嘗試使用: '{db_path_str}'")
        path = Path(db_path_str)
        if path.is_file(): return path
        else:
            print(f"❌ 手動指定路徑錯誤: '{db_path_str}' 不是一個有效的檔案。")
            return None

    print("🚀 正在自動搜尋 'queue.db' 檔案...")
    search_dir = Path("/content") if Path("/content").exists() else Path("/")
    possible_paths = list(search_dir.rglob('queue.db'))

    if len(possible_paths) == 1:
        db_path = possible_paths[0]
        print(f"✅ 自動找到唯一的資料庫檔案於: {db_path}")
        return db_path
    elif len(possible_paths) > 1:
        print("⚠️ 找到多個 'queue.db' 檔案。請從下方列表中複製正確的路徑，")
        print("   並將其貼到上方的 'db_path_str' 欄位中，然後重新執行儲存格。")
        for p in possible_paths: print(f"  - {p}")
        return None
    else:
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
            print(f"❌ 上傳檔案時發生錯誤: {e}", file=sys.stderr)
            return None

def generate_task_report(conn: sqlite3.Connection):
    """產生並印出任務報告。"""
    print("\n" + "="*38 + " (A) 任務報告 " + "="*38 + "\n")

    selected_statuses = []
    if 顯示已完成: selected_statuses.append('completed')
    if 顯示已失敗: selected_statuses.append('failed')
    if 顯示處理中: selected_statuses.append('processing')
    if 顯示待處理: selected_statuses.append('pending')

    if not selected_statuses:
        print("ℹ️ 您沒有選擇任何任務狀態，因此不顯示任務報告。")
        return

    print(f"篩選任務狀態: {', '.join(selected_statuses)}")

    try:
        cursor = conn.cursor()
        query_placeholders = ','.join(['?'] * len(selected_statuses))
        sql_query = f"SELECT * FROM tasks WHERE status IN ({query_placeholders}) ORDER BY created_at DESC"
        cursor.execute(sql_query, selected_statuses)
        tasks = cursor.fetchall()

        if not tasks:
            print("➡️ 在指定的狀態下，找不到任何任務記錄。")
        else:
            print(f"➡️ 找到了 {len(tasks)} 筆任務記錄。\n")
            for task in tasks:
                log_parts = [
                    "="*80,
                    f"任務 ID  : {task['task_id']}",
                    f"任務類型 : {task['type'].upper()}",
                    f"狀態     : {task['status'].upper()}",
                    f"建立時間 : {task['created_at']}",
                    f"更新時間 : {task['updated_at']}",
                    "-"*80
                ]
                # Payload
                payload_str = task['payload']
                log_parts.append("▼ 任務 Payload:")
                if payload_str:
                    try: log_parts.append(json.dumps(json.loads(payload_str), indent=2, ensure_ascii=False))
                    except json.JSONDecodeError: log_parts.append(payload_str)
                else: log_parts.append("(無)")
                # Result
                result_str = task['result']
                log_parts.append("▼ 任務 Result:")
                if result_str:
                    try: log_parts.append(json.dumps(json.loads(result_str), indent=2, ensure_ascii=False))
                    except json.JSONDecodeError: log_parts.append(result_str)
                else: log_parts.append("(無)")
                log_parts.append("="*80)
                print("\n".join(log_parts))
                print("\n")

    except sqlite3.Error as e:
        print(f"❌ 讀取 `tasks` 表時發生錯誤: {e}", file=sys.stderr)

def generate_system_log_report(conn: sqlite3.Connection):
    """產生並印出系統日誌報告。"""
    print("\n" + "="*37 + " (B) 系統日誌報告 " + "="*37 + "\n")

    selected_sources = []
    if 顯示_Orchestrator: selected_sources.append('orchestrator')
    if 顯示_Worker: selected_sources.append('worker')
    if 顯示_API_Server: selected_sources.append('api_server')

    selected_levels = []
    if 顯示_INFO: selected_levels.append('INFO')
    if 顯示_WARNING: selected_levels.append('WARNING')
    if 顯示_ERROR: selected_levels.append('ERROR')
    if 顯示_CRITICAL: selected_levels.append('CRITICAL')

    if not selected_sources or not selected_levels:
        print("ℹ️ 您沒有選擇任何日誌來源或等級，因此不顯示系統日誌。")
        return

    print(f"篩選日誌來源: {', '.join(selected_sources)}")
    print(f"篩選日誌等級: {', '.join(selected_levels)}")

    try:
        cursor = conn.cursor()

        source_ph = ','.join(['?'] * len(selected_sources))
        level_ph = ','.join(['?'] * len(selected_levels))

        sql_query = f"SELECT * FROM system_logs WHERE source IN ({source_ph}) AND level IN ({level_ph}) ORDER BY timestamp ASC"
        params = selected_sources + selected_levels

        cursor.execute(sql_query, params)
        logs = cursor.fetchall()

        if not logs:
            print("➡️ 在指定的篩選條件下，找不到任何系統日誌。")
        else:
            print(f"➡️ 找到了 {len(logs)} 筆系統日誌記錄。\n")
            for log in logs:
                print(f"{log['timestamp']} | {log['source']:<12} | {log['level']:<8} | {log['message']}")

    except sqlite3.Error as e:
        print(f"❌ 讀取 `system_logs` 表時發生錯誤: {e}", file=sys.stderr)


def main():
    """主執行函數"""
    db_path = find_or_upload_db()
    if not db_path:
        print("\n無法定位資料庫檔案，腳本終止。")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        if 顯示任務報告:
            generate_task_report(conn)

        if 顯示系統日誌:
            generate_system_log_report(conn)

        if not 顯示任務報告 and not 顯示系統日誌:
            print("您未選擇顯示任何報告，腳本已結束。")

    except sqlite3.Error as e:
        print(f"❌ 連接資料庫或執行報告時發生錯誤: {e}", file=sys.stderr)
    finally:
        if 'conn' in locals() and conn:
            conn.close()
        print("\n" + "="*40 + " 報告結束 " + "="*40)

# --- 執行 ---
if __name__ == "__main__":
    main()
