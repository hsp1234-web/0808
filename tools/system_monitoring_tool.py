#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系統監控獨立工具 (System Monitoring Tool) - v2 (烘烤模式)

功能:
1.  啟動時檢查並解壓縮預烘烤的虛擬環境。
2.  使用看門狗（Watchdog）計時器，防止腳本意外卡死。
3.  獲取當前的 CPU 和記憶體使用率，並以 JSON 格式輸出。
"""
import os
import sys
import time
import json
import signal
import tarfile
import shutil
from pathlib import Path

# --- 設定 ---
TOOL_NAME = "SystemMonitoringTool"
VENV_DIR = Path(__file__).parent / f".venv_{Path(__file__).stem}"
BAKED_ENV_ARCHIVE = Path(__file__).parent.parent / "storage" / "baked_envs" / f"{VENV_DIR.name}.tar.xz"
WATCHDOG_TIMEOUT = 15

# --- 依賴列表 (僅供參考) ---
DEPENDENCIES = {
    "pydantic": "pydantic==2.11.7",
    "psutil": "psutil==7.0.0",
}

# --- 日誌記錄 ---
def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}][{TOOL_NAME}] {message}", file=sys.stderr)

# --- 看門狗 ---
class Watchdog:
    def __init__(self, seconds):
        self.seconds = seconds
    def __enter__(self):
        signal.signal(signal.SIGALRM, self._handle_timeout)
        signal.alarm(self.seconds)
        log(f"🛡️ 看門狗已啟動，超時設定為 {self.seconds} 秒。")
    def __exit__(self, exc_type, exc_value, traceback):
        signal.alarm(0)
        log("✅ 看門狗已解除。")
    def _handle_timeout(self, signum, frame):
        log(f"❌ 看門狗錯誤：腳本執行超過 {self.seconds} 秒，強制終止。")
        sys.exit(1)

# --- 環境準備 ---
def prepare_environment():
    if VENV_DIR.exists():
        log(f"✅ 虛擬環境 '{VENV_DIR.name}' 已存在。")
        return
    log(f"🔍 虛擬環境 '{VENV_DIR.name}' 不存在，正在尋找預烘烤的存檔...")
    if not BAKED_ENV_ARCHIVE.exists():
        log(f"❌ 嚴重錯誤：找不到預烘烤的環境存檔: {BAKED_ENV_ARCHIVE}")
        log("   請先執行 'python scripts/bake_tool_envs.py' 來建立環境存檔。")
        sys.exit(1)
    log(f"📦 找到存檔，正在解壓縮至 '{VENV_DIR.parent}' (使用 xz)...")
    try:
        with tarfile.open(BAKED_ENV_ARCHIVE, "r:xz") as tar:
            tar.extractall(path=VENV_DIR.parent)
        log("✅ 環境解壓縮成功。")
    except Exception as e:
        log(f"❌ 解壓縮環境時發生錯誤: {e}")
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR)
        sys.exit(1)

def activate_venv():
    site_packages = VENV_DIR / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if os.name == 'nt':
        site_packages = VENV_DIR / "Lib" / "site-packages"
    if not site_packages.exists():
        log(f"❌ 嚴重錯誤：在虛擬環境中找不到 site-packages 目錄: {site_packages}")
        sys.exit(1)
    log(f"🔌 正在將 '{site_packages}' 加入到 sys.path")
    sys.path.insert(0, str(site_packages))

# --- 核心功能 ---
def get_system_usage():
    import psutil
    from pydantic import BaseModel

    class SystemUsage(BaseModel):
        cpu_percent: float
        memory_percent: float

    log("💡 正在獲取系統使用率...")
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory_info = psutil.virtual_memory()
    usage_data = SystemUsage(
        cpu_percent=cpu_percent,
        memory_percent=memory_info.percent
    )
    log(f"📊 CPU: {cpu_percent}%, Memory: {memory_info.percent}%")
    print(usage_data.model_dump_json())

def main():
    log("--- 系統監控工具已啟動 (v2 烘烤模式) ---")
    with Watchdog(WATCHDOG_TIMEOUT):
        prepare_environment()
        activate_venv()
        get_system_usage()
    log("--- 系統監控工具執行完畢 ---")

if __name__ == "__main__":
    main()
