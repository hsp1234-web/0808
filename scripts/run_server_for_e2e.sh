#!/bin/bash

# 啟用作業控制
set -m

# --- 清理函式 ---
# 此函式會在腳本接收到 EXIT 信號時被調用
cleanup() {
    echo "接收到退出信號，正在清理背景進程..."
    # 殺掉所有由此腳本啟動的背景進程
    # pkill -P $$ 會殺掉所有父 ID 為目前腳本 PID 的進程
    pkill -P $$
    echo "清理完畢。"
}

# --- 信號捕捉 ---
# 使用 trap 命令，在腳本退出時（無論是正常結束還是被中斷）執行 cleanup 函式
# 這確保了子進程總能被清理
trap cleanup EXIT

# --- 啟動後端服務 ---
echo "正在啟動後端服務..."

# 1. 啟動資料庫管理器
# 假設 'python' 是正確的直譯器
python src/db/manager.py &

# 2. 啟動 API 伺服器
# 使用與 circus.ini 相同的設定
API_MODE=mock python src/api/api_server.py --port 42649 &

echo "後端服務已啟動。等待所有背景作業..."

# --- 等待 ---
# wait 命令會暫停腳本，直到所有背景作業都結束
# 當 Playwright 終止此腳本時，trap 會被觸發，清理函式會執行，
# 然後 wait 會因為所有子進程被殺掉而結束，最後腳本退出。
wait
