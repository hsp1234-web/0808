# -*- coding: utf-8 -*-
import os
import sys
import subprocess

def main():
    """
    一個簡單的本地啟動腳本，用於開發和測試。
    它會安裝依賴，然後使用 subprocess.run 啟動 Uvicorn，以確保路徑正確。
    """
    print("==========================================================")
    print("🚀 鳳凰之心 - 本地開發啟動器 (v2 - Subprocess Runner)")
    print("==========================================================")

    # --- 步驟 1: 安裝依賴 ---
    print("\n--- [步驟 1/2] 正在檢查並安裝依賴 ---")
    try:
        # 使用 -qq 來極度簡化輸出，只在錯誤時顯示信息
        print("📦 正在安裝核心依賴 (from requirements.txt)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-qq", "-r", "requirements.txt"], check=True)

        print("📦 正在安裝轉錄工作者依賴 (from requirements-worker.txt)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-qq", "-r", "requirements-worker.txt"], check=True)
        print("✅ 所有依賴安裝完成。")
    except subprocess.CalledProcessError as e:
        print(f"❌ 依賴安裝失敗: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ 找不到 requirements.txt 或 requirements-worker.txt。")
        sys.exit(1)

    # --- 步驟 2: 啟動 Uvicorn 伺服器 ---
    print("\n--- [步驟 2/2] 正在啟動 FastAPI 伺服器 ---")
    host = "0.0.0.0"
    port = "8000"
    print(f"✅ 伺服器將在 http://{host}:{port} 上運行")
    print("💡 使用 Ctrl+C 來停止伺服器。")

    # 使用 python -m uvicorn 來啟動，這是更穩健的方式
    # 它能更好地處理模組路徑問題，特別是對於子進程重載
    uvicorn_command = [
        sys.executable,
        "-m", "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", port,
        "--reload"
    ]

    # 執行命令。這個呼叫是阻塞的，會將 Uvicorn 的日誌直接輸出到此處。
    subprocess.run(uvicorn_command)

if __name__ == "__main__":
    main()
