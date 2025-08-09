# Colab 啟動器 (colab_run.py)
# 專為 Colab 環境設計的極簡啟動腳本，讓服務持續運行。
import subprocess
import sys
import os

def main():
    """
    在 Colab 環境中啟動協調器。
    """
    print("🚀 Colab Runner: Starting the main orchestrator...")

    # 確保此腳本可以找到 orchestrator.py
    orchestrator_script = os.path.join(os.path.dirname(__file__), "orchestrator.py")

    if not os.path.exists(orchestrator_script):
        print(f"❌ Error: Cannot find orchestrator script at {orchestrator_script}")
        sys.exit(1)

    try:
        # 使用 sys.executable 確保我們用的是同一個 Python 解譯器
        process = subprocess.Popen(
            [sys.executable, orchestrator_script],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        # 等待協調器程序結束
        process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Colab Runner: Received interrupt, shutting down.")
        process.terminate()
    except Exception as e:
        print(f"🔥 Colab Runner: An error occurred: {e}")
        if process:
            process.kill()

if __name__ == "__main__":
    main()
