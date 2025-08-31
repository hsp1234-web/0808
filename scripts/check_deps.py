# scripts/check_deps.py
import sys
import importlib
import re

def get_package_name(req_line: str) -> str:
    """從 requirements.txt 的一行中提取基礎套件名稱。"""
    # 移除版本說明、註解和額外項目
    match = re.match(r"^\s*([a-zA-Z0-9_.-]+)", req_line)
    if not match:
        return None

    # 處理常見的命名不一致情況
    name = match.group(1).strip()
    if name == 'yt-dlp':
        return 'yt_dlp'
    if name == 'google-generativeai':
        return 'google.generativeai'
    if name == 'python-dotenv':
        return 'dotenv'
    if name == 'opencc-python-reimplemented':
        return 'opencc'
    # 處理帶有 extras 的情況，例如 uvicorn[standard]
    return name.split('[')[0].replace('-', '_')

def main():
    """
    接收一個 requirements.txt 檔案路徑作為參數。
    檢查檔案中的每個套件是否可以被 import。
    將無法 import 的原始行輸出到 stdout。
    """
    if len(sys.argv) != 2:
        print("用法: python check_deps.py <requirements_file_path>", file=sys.stderr)
        sys.exit(1)

    req_file_path = sys.argv[1]
    missing_reqs = []

    try:
        with open(req_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                pkg_name = get_package_name(line)
                if not pkg_name:
                    continue

                try:
                    importlib.import_module(pkg_name)
                except ImportError:
                    # 如果無法導入，則認為該套件缺失
                    missing_reqs.append(line)
    except FileNotFoundError:
        # 如果需求檔案本身不存在，我們視為所有套件都缺失（讓 pip 處理）
        # 但在我們的案例中，這應該不會發生，因為我們會先合併檔案。
        # 為防萬一，直接印出錯誤並退出。
        print(f"錯誤: 找不到需求檔案 '{req_file_path}'", file=sys.stderr)
        sys.exit(1)

    # 將所有缺失的套件的原始行印出，每行一個
    if missing_reqs:
        print("\n".join(missing_reqs))

if __name__ == "__main__":
    main()
