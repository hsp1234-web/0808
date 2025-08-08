# app/queue.py
import queue

# 建立一個全域的、執行緒安全的任務佇列
# 這個佇列將用於在 Web 伺服器 (main.py) 和背景工作者 (worker.py) 之間傳遞任務
# 佇列中將存放元組 (task_id, file_path)
task_queue = queue.Queue()
