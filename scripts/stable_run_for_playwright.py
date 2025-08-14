# scripts/stable_run_for_playwright.py
import sys
import os
import uvicorn
from pathlib import Path

# 將 src 目錄加入 Python 路徑，以確保可以找到 api_server 模組
# __file__ 是 'scripts/stable_run_for_playwright.py'
# .parent 是 'scripts/'
# .parent.parent 是專案根目錄
# .parent.parent / 'src' 是 'src/'
src_path = str(Path(__file__).resolve().parent.parent / "src")
sys.path.insert(0, src_path)

# 現在我們可以安全地從 src 中的模組匯入
from api.api_server import app, log

def main():
    """
    一個穩定、可靠的後端伺服器啟動器，專為 Playwright E2E 測試設計。
    此腳本透過直接匯入和執行 uvicorn.run() 來啟動伺服器，
    完全避免了在沙盒環境中有問題的 subprocess.Popen 指令。
    """
    log.info("--- 穩定版 Playwright 測試伺服器啟動器 ---")

    # 設定必要的環境變數，以確保測試在一致的模擬模式下運行
    os.environ['API_MODE'] = 'mock'
    os.environ['FORCE_MOCK_TRANSCRIBER'] = 'true'
    log.info(f"環境變數 API_MODE 已設為: {os.environ['API_MODE']}")
    log.info(f"環境變數 FORCE_MOCK_TRANSCRIBER 已設為: {os.environ['FORCE_MOCK_TRANSCRIBER']}")

    # 清理舊的資料庫檔案，確保測試隔離性
    db_file = Path(src_path) / "db" / "queue.db"
    if db_file.exists():
        log.info(f"--- 正在清理舊的資料庫檔案 ({db_file}) ---")
        try:
            db_file.unlink()
            log.info("✅ 舊資料庫已刪除。")
        except OSError as e:
            log.error(f"刪除資料庫時出錯: {e}")

    # 固定的測試埠號
    port = 42649
    log.info(f"🚀 準備在 http://127.0.0.1:{port} 上啟動 API 伺服器...")

    try:
        # 直接以程式化方式執行 uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info" # 可以在此處控制日誌等級
        )
    except Exception as e:
        log.critical(f"💥 啟動 uvicorn 時發生致命錯誤: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
