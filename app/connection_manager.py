"""WebSocket ulanishlarni foydalanuvchi bo'yicha boshqaradi (bir user — bir nechta qurilma)."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("ws")


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> set(WebSocket)  (bir foydalanuvchi bir necha tab/qurilmadan ulanishi mumkin)
        self.active: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self.active[user_id].add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self.active.get(user_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    self.active.pop(user_id, None)

    async def send_to_user(self, user_id: int, data: dict) -> None:
        """Bitta foydalanuvchining barcha lokal ulanishlariga yuboradi."""
        conns = list(self.active.get(user_id, set()))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(user_id, ws)

    async def send_to_users(self, user_ids: list[int], data: dict) -> None:
        for uid in user_ids:
            await self.send_to_user(uid, data)


# Global instance
manager = ConnectionManager()
