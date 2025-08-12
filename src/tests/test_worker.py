import unittest
import uuid
import json
from pathlib import Path
import shutil
import os

import worker
from db import database

class TestWorker(unittest.TestCase):
    """
    測試 worker.py 的核心功能，特別是基於資料庫的任務處理流程。
    """

    def setUp(self):
        """設定一個乾淨的測試環境。"""
        self.test_id = uuid.uuid4().hex[:8]
        self.root_dir = Path("/tmp") / f"phoenix_test_{self.test_id}"

        # 1. 設定路徑
        self.db_path = self.root_dir / "db"
        self.db_file = self.db_path / "queue.db"
        self.transcripts_dir = self.root_dir / "transcripts"
        self.mock_audio_dir = self.root_dir / "mock_audio"

        # 2. 建立目錄
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(exist_ok=True)
        self.mock_audio_dir.mkdir(exist_ok=True)

        # 3. Monkeypatch 資料庫和路徑常數，使其指向我們的測試目錄
        #    這樣可以隔離測試，避免影響開發環境中的真實資料
        self.original_db_file = database.DB_FILE
        self.original_transcripts_dir = worker.TRANSCRIPTS_DIR
        database.DB_FILE = self.db_file
        worker.TRANSCRIPTS_DIR = self.transcripts_dir

        # 4. 初始化資料庫
        database.initialize_database()

        # 5. 建立一個假的音訊檔案
        self.mock_audio_file = self.mock_audio_dir / "test_audio.wav"
        self.mock_audio_file.touch()

    def tearDown(self):
        """清理測試環境。"""
        # 還原 monkeypatched 的常數
        database.DB_FILE = self.original_db_file
        worker.TRANSCRIPTS_DIR = self.original_transcripts_dir

        # 刪除測試目錄
        if self.root_dir.exists():
            shutil.rmtree(self.root_dir)

    def test_mock_transcription_workflow(self):
        """
        測試一個完整的模擬轉錄任務流程：
        1. 在資料庫中建立一個任務。
        2. 直接呼叫 worker 的處理函式。
        3. 驗證資料庫中的狀態和檔案系統中的結果。
        """
        # 1. 準備任務
        task_id = f"task_{uuid.uuid4().hex}"
        payload = {
            "input_file": str(self.mock_audio_file),
            "model_size": "tiny",
            "language": "en"
        }

        # 為了讓測試更貼近真實情況，我們將任務加入資料庫
        # 但為了測試的原子性，我們不依賴 `fetch_and_lock_task`
        # 而是手動建立一個 task 物件傳給處理函式
        add_success = database.add_task(task_id, json.dumps(payload))
        self.assertTrue(add_success, "任務應成功加入資料庫")

        # 建立一個與 worker 從資料庫中讀取時結構相同的 task dict
        task_to_process = {
            "task_id": task_id,
            "payload": json.dumps(payload),
            "type": "transcribe"
        }

        # 2. 執行處理函式 (使用模擬模式)
        worker.process_transcription_task(task_to_process, use_mock=True)

        # 3. 驗證結果
        # 3a. 驗證資料庫狀態
        final_status = database.get_task_status(task_id)
        self.assertIsNotNone(final_status, "應能在資料庫中找到任務狀態")
        self.assertEqual(final_status["status"], "completed", "任務狀態應為 'completed'")

        # 3b. 驗證結果檔案
        expected_output_file = self.transcripts_dir / f"{task_id}.txt"
        self.assertTrue(expected_output_file.exists(), "結果檔案應在 transcripts 目錄中被建立")

        content = expected_output_file.read_text(encoding='utf-8')
        # 驗證內容是否符合 mock_transcriber.py 的實際輸出
        self.assertIn("歡迎使用鳳凰音訊轉錄儀", content, "結果檔案的內容應為模擬的中文轉錄文字")

if __name__ == '__main__':
    unittest.main()
