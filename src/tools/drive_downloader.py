import gdown
import os
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_file(url: str, output_dir: str, file_name: str = None) -> str:
    """
    從指定的 URL 下載檔案，特別針對 Google Drive 連結進行了優化。

    :param url: 要下載的檔案 URL。
    :param output_dir: 儲存下載檔案的目錄。
    :param file_name: (可選) 指定儲存的檔案名稱。若為 None，則嘗試從 URL 或 gdown 推斷。
    :return: 下載完成後的檔案完整路徑。如果失敗則回傳 None。
    """
    os.makedirs(output_dir, exist_ok=True)

    # 如果未指定檔案名稱，則使用 gdown 的預設行為
    output_path = os.path.join(output_dir, file_name) if file_name else output_dir

    logging.info(f"準備從 URL 下載：{url}")
    logging.info(f"將儲存至：{output_path}")

    try:
        # 使用 gdown 下載，fuzzy=True 可幫助解析 Google Drive 的預覽/文件連結
        downloaded_path = gdown.download(url, output_path, quiet=False, fuzzy=True)

        if downloaded_path and os.path.exists(downloaded_path):
            logging.info(f"✅ 檔案成功下載至：{downloaded_path}")
            return downloaded_path
        else:
            # 這種情況很少見，但以防萬一
            logging.error("❌ 下載失敗：gdown 執行完畢但未回傳有效的檔案路徑。")
            return None

    except Exception as e:
        logging.error(f"❌ 下載過程中發生嚴重錯誤：{e}")
        return None

if __name__ == '__main__':
    # 這是一個當此檔案被直接執行時的測試區塊
    print("正在執行 drive_downloader.py 的單元測試...")

    test_urls = {
        "lai_jie_6799_file.pdf": "https://drive.google.com/file/d/1RUl7XhxyJpxKO4RBX0AxeeyD4ABYPU_l/view?usp=sharing",
        "jing_que_3162_doc.pdf": "https://docs.google.com/document/d/16TkL54YmFAToS1UR26VdV_mYgr8bCAml/edit?tab=t.0"
    }

    test_output_dir = "/app/temp_test_downloads"

    for name, url in test_urls.items():
        print(f"\n--- 測試下載: {name} ---")
        path = download_file(url, test_output_dir, file_name=name)
        if path:
            print(f"✔️ 測試成功，檔案位於: {path}")
        else:
            print(f"❌ 測試失敗")

    print("\n單元測試完畢。")
