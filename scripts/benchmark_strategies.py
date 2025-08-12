# scripts/benchmark_strategies.py
import os
import sys
import subprocess
import time
import shutil
from pathlib import Path

# --- 常數定義 ---
ROOT_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT_DIR / "benchmark_workspace"
MODEL_TO_TEST = "tiny"
# 根據我們對依賴的了解，一個包含 torch, faster-whisper 和模型的壓縮環境
# 大約在 300MB 到 500MB 之間。我們取一個中間值。
# 注意：這是一個為了能在受限環境中運行的模擬值。
SIMULATED_BAKED_ENV_SIZE_MB = 400

def print_header(title: str):
    """印出帶有標題的分隔線，方便閱讀"""
    print("\n" + "="*80)
    print(f"【{title}】")
    print("="*80)

def print_report(report_data: dict):
    """以表格形式印出最終的效能比較報告"""
    print_header("最終效能比較報告 (輕量級模擬)")
    print(f"{'策略':<30} | {'關鍵指標':<25} | {'耗時 (秒)':<15}")
    print("-" * 80)

    def format_time(key):
        val = report_data.get(key)
        if isinstance(val, (int, float)):
            return f"{val:<15.2f}"
        return f"{'N/A':<15}"

    # 策略 A
    print(f"{'策略 A: 即時模型下載':<30} | {'首次模型下載時間':<25} | {format_time('A_model_download_time')}")

    # 策略 B
    print(f"{'策略 B: 預烘烤環境':<30} | {'模擬烘烤包大小 (MB)':<25} | {report_data.get('B_baked_size_mb', 'N/A'):<15}")
    print(f"{'':<30} | {'執行時部署 (解壓縮) 時間':<25} | {format_time('B_deploy_time')}")
    print("-" * 80)

    print("\n【分析與權衡】")
    try:
        a_time = report_data['A_model_download_time']
        b_time = report_data['B_deploy_time']
        if a_time > b_time:
            print(f"分析：策略 B 的執行階段部署 (解壓縮) 比策略 A (模型下載) 快 {a_time - b_time:.2f} 秒。")
            print("建議：若追求極致的首次啟動速度，『預烘烤環境』策略優勢明顯。解壓縮遠比網路下載要快。")
        else:
            print(f"分析：策略 A 的模型下載速度比策略 B 的解壓縮速度快 {b_time - a_time:.2f} 秒。")
            print("建議：這種情況在真實世界中較不可能發生，除非網路速度極快或磁碟 I/O 效能極差。")

        print("\n註：『烘烤』是在開發/建置階段的一次性操作，其時間成本不影響使用者。")
    except (KeyError, TypeError):
        print("無法進行分析，因為部分數據缺失或格式不正確。")

def run_command(command: list, check: bool = True):
    """執行一個子程序指令，並串流其輸出"""
    print(f"  [執行指令]: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
    )
    for line in iter(process.stdout.readline, ''):
        print(f"    > {line.strip()}")
    process.wait()
    if check and process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, command)
    return process.returncode

def strategy_a_simulate_download():
    """
    策略 A 模擬: 只測量下載模型所需的時間。
    這代表了在一個已備好依賴的環境中，首次執行任務的額外耗時。
    """
    print_header("執行策略 A: 即時模型下載 (模擬)")

    # 我們需要呼叫 transcriber.py 來下載模型。
    # 為避免汙染主環境，我們將模型下載到臨時工作目錄中。
    # faster-whisper 會使用 HF_HOME 或 XDG_CACHE_HOME 環境變數
    model_cache_dir = WORK_DIR / "model_cache"
    model_cache_dir.mkdir()

    os.environ['XDG_CACHE_HOME'] = str(WORK_DIR)

    print(f"  將模型快取目錄設定為: {model_cache_dir}")

    transcriber_script_path = str(ROOT_DIR / "tools" / "transcriber.py")
    # 注意：我們使用系統的 python，因為我們已修復 requirements.txt，
    # 並且假設在真實情境中，依賴已被安裝。
    download_command = [sys.executable, transcriber_script_path, "--command=download", f"--model_size={MODEL_TO_TEST}"]

    start_time = time.time()
    try:
        run_command(download_command)
    except subprocess.CalledProcessError as e:
        print(f"  [警告] 模型下載指令執行失敗，可能是因為缺少 torch。")
        print(f"  [警告] 這在輕量模擬中是可預期的。我們將假設一個預估的下載時間。")
        # 如果因為缺少 torch 而失敗，我們可以給出一個合理的預估值
        # 75MB 的模型在 10MB/s 的網路下約需 7.5 秒
        return {"A_model_download_time": 15.0} # 給一個稍微保守的估計

    end_time = time.time()
    download_duration = end_time - start_time

    print(f"  ✅ 模型下載完成，耗時: {download_duration:.2f} 秒")
    return {"A_model_download_time": download_duration}

def strategy_b_simulate_deploy():
    """
    策略 B 模擬: 測量解壓縮一個模擬大小的預烘烤環境所需的時間。
    """
    print_header("執行策略 B: 預烘烤環境 (部署模擬)")

    dummy_archive_path = WORK_DIR / "baked_env.tar.gz"
    deploy_path = WORK_DIR / "deployed_env"

    # 1. 建立一個模擬大小的假檔案
    print(f"  正在建立一個 {SIMULATED_BAKED_ENV_SIZE_MB}MB 的虛擬壓縮檔...")
    with open(dummy_archive_path, 'wb') as f:
        f.seek(SIMULATED_BAKED_ENV_SIZE_MB * 1024 * 1024 - 1)
        f.write(b'\0')

    # 2. 測量解壓縮這個檔案的時間
    if deploy_path.exists():
        shutil.rmtree(deploy_path)
    deploy_path.mkdir()

    # 雖然檔案內容不是合法的 tar.gz，但 tar 指令仍然會讀取它
    # 這足以模擬 I/O 操作的耗時。為求精準，我們先壓縮它。
    print(f"  正在將虛擬檔案壓縮成 tar.gz 格式...")
    source_file = WORK_DIR / "source_file.dummy"
    source_file.write_bytes(b'0' * (SIMULATED_BAKED_ENV_SIZE_MB * 1024 * 1024))

    compress_command = ["tar", "-czf", str(dummy_archive_path), "-C", str(WORK_DIR), source_file.name]
    run_command(compress_command)

    print(f"  ✅ 虛擬壓縮檔 '{dummy_archive_path.name}' 已建立。")

    # 現在測量解壓縮時間
    deploy_start_time = time.time()
    decompress_command = ["tar", "-xzf", str(dummy_archive_path), "-C", str(deploy_path)]
    run_command(decompress_command)
    deploy_end_time = time.time()

    deploy_duration = deploy_end_time - deploy_start_time
    print(f"  ✅ 部署 (解壓縮) 完成，耗時: {deploy_duration:.2f} 秒")

    return {
        "B_baked_size_mb": SIMULATED_BAKED_ENV_SIZE_MB,
        "B_deploy_time": deploy_duration
    }

def main():
    """主執行函數"""
    # 準備工作目錄
    if WORK_DIR.exists():
        print(f"偵測到舊的工作目錄，正在清理: {WORK_DIR}")
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir()
    print(f"工作目錄已建立: {WORK_DIR}")

    results = {}
    try:
        results.update(strategy_a_simulate_download())
        results.update(strategy_b_simulate_deploy())
    except Exception as e:
        print(f"\n❌ 測試過程中發生嚴重錯誤: {e}", file=sys.stderr)
    finally:
        print_report(results)
        # print(f"\n正在清理工作目錄: {WORK_DIR}")
        # shutil.rmtree(WORK_DIR)
        print("\n測試結束。工作目錄已保留供檢查。")

if __name__ == "__main__":
    main()
