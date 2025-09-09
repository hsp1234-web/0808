# src/api/sse_manager.py
"""
此模組提供一個基於 asyncio.Queue 的 Server-Sent Events (SSE) 廣播器。

它允許應用程式的不同部分將訊息廣播給所有連接到 SSE 端點的客戶端。
"""
import asyncio
import logging
from typing import Dict, Any, Set

log = logging.getLogger(__name__)

class SSEBroadcaster:
    """
    一個單例類，用於管理 SSE 客戶端的訂閱並向其廣播訊息。
    """
    def __init__(self):
        self._queues: Set[asyncio.Queue] = set()
        log.info("✅ SSE 廣播器已初始化。")

    async def subscribe(self) -> asyncio.Queue:
        """
        一個新的客戶端訂閱廣播。回傳一個專屬的佇列。
        """
        q = asyncio.Queue()
        self._queues.add(q)
        log.info(f"一個新的 SSE 客戶端已訂閱。目前訂閱數: {len(self._queues)}")
        return q

    def unsubscribe(self, q: asyncio.Queue):
        """
        客戶端取消訂閱。
        """
        if q in self._queues:
            self._queues.remove(q)
            log.info(f"一個 SSE 客戶端已離線。目前訂閱數: {len(self._queues)}")

    async def broadcast(self, message: Dict[str, Any]):
        """
        向所有已訂閱的客戶端廣播一條訊息。
        """
        if not self._queues:
            log.warning("沒有 SSE 客戶端在監聽，廣播訊息被捨棄。")
            return

        log.info(f"正在向 {len(self._queues)} 個 SSE 客戶端廣播訊息...")
        # 我們將任務放入一個集合中，以並行方式將訊息放入所有佇列
        tasks = [q.put(message) for q in self._queues]
        await asyncio.gather(*tasks)

# 建立一個全域單例，方便在應用程式各處引用
sse_broadcaster = SSEBroadcaster()

def get_sse_broadcaster() -> SSEBroadcaster:
    """
    回傳廣播器的單例。
    """
    return sse_broadcaster
