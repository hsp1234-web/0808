# scripts/run_dev.py
import uvicorn
import os
import sys
import threading

# 匯入我們的背景工作者函式
# 為了讓這個匯入能成功，我們需要先設定好 sys.path
# --- 設定 sys.path ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- 現在可以安全地匯入 ---
from app.worker import run_worker

def start():
    """
    在本地開發環境中啟動 Uvicorn 伺服器和背景工作者。
    """
    print("==================================================")
    print("🚀 正在啟動 鳳凰轉錄儀 完整開發環境...")
    print("==================================================")

    # 1. 在一個獨立的背景執行緒中啟動工作者
    # 將執行緒設定為 daemon=True，這樣當主程式退出時，此執行緒也會自動結束
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    print("✅ 背景工作者 (Worker) 已在獨立執行緒中啟動。")

    # 2. 在主執行緒中啟動 Uvicorn Web 伺服器
    print("✅ 準備啟動 Uvicorn Web 伺服器...")
    print("應用程式模組: app.main:app")
    print("主機: 127.0.0.1")
    print("埠號: 8000")
    print("\n請在瀏覽器中開啟 http://127.0.0.1:8000 來存取介面。")
    print("使用 Ctrl+C 來停止伺服器。")

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False, # 注意：當運行多個進程/執行緒時，reload 模式可能會導致問題。開發時建議分開啟動。
                     # 但為了整合測試，這裡暫時關閉 reload。
        log_level="info"
    )

if __name__ == "__main__":
    start()
