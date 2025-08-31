#!/bin/bash
# 說明：此腳本用於全面驗證專案環境是否已成功設定。
# 它會以清單形式檢查所有關鍵依賴的版本，並提供詳細列表，但不會進行任何安裝或修改。

echo "--- 正在開始環境驗證 ---"
echo ""

# --- 輔助函式 ---
check_pkg() {
  if dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; then
    echo "  ✅ $1: 已安裝"
  else
    echo "  ❌ $1: 未安裝"
  fi
}

# --- 1. 驗證核心工具 ---
echo ">>> 1/5: 正在驗證核心開發工具..."
echo "Python 版本:"
python --version
echo "Node.js 版本:"
node --version
echo "Bun 版本:"
bun --version
echo "uv 版本:"
uv --version
echo "---------------------------"
echo ""

# --- 2. 驗證系統級依賴 ---
echo ">>> 2/5: 正在驗證核心系統依賴..."
check_pkg "ffmpeg"
check_pkg "opencc"
check_pkg "build-essential"
# 抽查一個 Playwright 需要的關鍵函式庫
check_pkg "libnss3"
echo "---------------------------"
echo ""


# --- 3. 驗證 Node.js 套件 ---
echo ">>> 3/5: 正在驗證關鍵 Node.js 套件..."
echo "檢查關鍵 Node.js 套件的安裝狀態:"
if bun pm ls | grep -q "@playwright/test"; then
    echo "  ✅ @playwright/test: 已安裝"
else
    echo "  ❌ @playwright/test: 未安裝"
fi
echo ""
echo "已安裝的頂層 Node.js 套件列表:"
bun pm ls --depth=0
echo "---------------------------"
echo ""

# --- 4. 驗證 Python 套件 ---
echo ">>> 4/5: 正在驗證關鍵 Python 套件..."
echo "檢查關鍵 Python 套件的安裝狀態:"
INSTALLED_PYTHON_PACKAGES=$(uv pip list)
KEY_PYTHON_PACKAGES=("torch" "fastapi" "faster-whisper" "yt-dlp" "circus" "pydub" "requests" "google-generativeai" "WeasyPrint")
for pkg in "${KEY_PYTHON_PACKAGES[@]}"; do
  # ✨ 根據您的建議進行修正：加入 -i 旗標以忽略大小寫
  if echo "$INSTALLED_PYTHON_PACKAGES" | grep -i -q "$pkg"; then
    echo "  ✅ $pkg: 已安裝"
  else
    echo "  ❌ $pkg: 未安裝"
  fi
done
echo ""
echo "--- 完整 Python 套件列表 (uv pip list) ---"
uv pip list
echo "----------------------------------------"
echo ""

# --- 5. 驗證 Playwright 瀏覽器 ---
echo ">>> 5/5: 正在驗證 Playwright 瀏覽器..."
# 這個指令會顯示 Playwright 版本以及它所管理的瀏覽器
npx playwright --version
echo "---------------------------"
echo ""

echo "✅ 環境驗證完成！"
echo "如果上方清單顯示所有項目均為「已安裝」，代表您的環境已準備就緒。"

