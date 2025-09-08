# src/shared/constants.py

# --- 任務狀態 (Task Statuses) ---
# 使用常數來定義任務狀態，可以避免在程式碼中因為拼寫錯誤或不一致
# (例如 'completed' vs '已完成') 而導致的隱性錯誤。
# 這是前後端之間關於任務狀態的「單一事實來源」(Single Source of Truth)。

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


# --- 任務類型 (Task Types) ---
# 同樣地，將任務類型也定義為常數。

TASK_TYPE_TRANSCRIBE = "transcribe"
TASK_TYPE_YOUTUBE_DOWNLOAD = "youtube_download"
TASK_TYPE_YOUTUBE_DOWNLOAD_ONLY = "youtube_download_only"
TASK_TYPE_GEMINI_PROCESS = "gemini_process"
