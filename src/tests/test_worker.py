import unittest
import sys
import time
import shutil
from pathlib import Path

# 將專案根目錄加入 sys.path 以便匯入 phoenix_runner
# 這確保測試可以在任何地方被執行
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import phoenix_runner

class TestWorkerFlow(unittest.TestCase):
    """
    測試新的、基於檔案系統輪詢的背景工作流程。
    這個測試不啟動網頁伺服器，而是直接呼叫 phoenix_runner，
    以驗證核心的後端邏輯是否正確。
    """

    def setUp(self):
        """在每個測試前執行，用於設定乾淨的測試環境。"""
        self.test_dir = ROOT_DIR / "temp_integration_test"
        self.pending_dir = self.test_dir / "tasks_pending"
        self.completed_dir = self.test_dir / "tasks_completed"

        # 建立測試目錄
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nSetting up test environment in {self.test_dir}")

    def tearDown(self):
        """在每個測試後執行，用於清理測試環境。"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        print(f"Tore down test environment at {self.test_dir}")

    def test_mock_transcription_workflow(self):
        """
        測試一個完整的模擬轉錄任務流程：
        1. 建立一個任務檔案。
        2. 使用 phoenix_runner 執行模擬轉錄。
        3. 驗證結果檔案是否被正確地建立。
        """
        print("Running test_mock_transcription_workflow...")
        # 1. 準備任務
        task_id = "test_task_01"
        # 在真實流程中，這會是一個音訊檔。在測試中，一個空檔案就足夠了。
        input_file = self.pending_dir / f"{task_id}.wav"
        input_file.touch()
        self.assertTrue(input_file.exists())

        # 預期的輸出檔案路徑
        output_file = self.completed_dir / f"{task_id}.txt"

        # 2. 執行工具
        try:
            proc = phoenix_runner.run(
                "transcriber",
                args=[str(input_file), str(output_file)],
                mock=True
            )
            # 等待程序結束。在真實應用中這會是非同步的。
            proc.wait(timeout=20)

            # 驗證程序成功退出
            self.assertEqual(proc.returncode, 0, "模擬工具程序應以返回碼 0 結束")

        except phoenix_runner.ToolExecutionError as e:
            self.fail(f"Phoenix runner 執行失敗: {e}")
        except Exception as e:
            self.fail(f"測試過程中發生未預期的錯誤: {e}")

        # 3. 驗證結果
        print("Verifying results...")
        self.assertTrue(output_file.exists(), "結果檔案應在 completed 目錄中被建立")

        content = output_file.read_text(encoding='utf-8')
        self.assertIn("mock_transcriber.py", content, "結果檔案的內容應表明它來自模擬工具")
        self.assertIn(str(input_file.name), content, "結果檔案的內容應包含輸入檔案的名稱")

        print("Test completed successfully.")

if __name__ == '__main__':
    unittest.main()
