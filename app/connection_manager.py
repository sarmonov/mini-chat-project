"""WebSocket ulanishlarni xonalar bo'yicha boshqaradi."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("ws")


class ConnectionManager:
    def __init__(self) -> None:
        # room -> {username: WebSocket}
        self.active: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, room: str, username: str, websocket: WebSocket) -> None:
        async with self._lock:
            self.active[room][username] = websocket

    async def disconnect(self, room: str, username: str) -> None:
        async with self._lock:
            self.active.get(room, {}).pop(username, None)

    async def broadcast(self, room: str, data: dict) -> None:
        """Xonadagi barcha ulanishlarga JSON yuboradi. O'lik socketlarni tozalaydi."""
        # nusxa olamiz, chunki yuborish vaqtida dict o'zgarishi mumkin
        connections = list(self.active.get(room, {}).items())
        dead: list[str] = []
        for username, ws in connections:
            try:
                await ws.send_json(data)
            except Exception:  # noqa: BLE001
                dead.append(username)
        for username in dead:
            await self.disconnect(room, username)

    async def send_personal(self, websocket: WebSocket, data: dict) -> None:
        await websocket.send_json(data)


# Global instance
manager = ConnectionManager()
