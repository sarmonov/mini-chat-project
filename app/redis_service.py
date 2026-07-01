"""Redis — presence (online/last seen), typing, pub/sub (realtime fan-out)."""
import json
from typing import Any, AsyncIterator, Optional

from redis.asyncio import Redis

from app.config import settings


class RedisService:
    def __init__(self) -> None:
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis ulanmagan. Avval connect() chaqiring.")
        return self._client

    async def connect(self) -> None:
        self._client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ---------- Presence (online status) ----------

    def _presence_key(self, user_id: int) -> str:
        return f"presence:{user_id}"

    async def mark_online(self, user_id: int) -> None:
        """Online belgisi + TTL (heartbeat). Ulanish sonini oshiradi."""
        await self.client.incr(f"conn:{user_id}")
        await self.client.set(self._presence_key(user_id), "1", ex=settings.PRESENCE_TTL)

    async def heartbeat(self, user_id: int) -> None:
        await self.client.set(self._presence_key(user_id), "1", ex=settings.PRESENCE_TTL)

    async def mark_offline(self, user_id: int) -> int:
        """Ulanish sonini kamaytiradi. 0 bo'lsa presence o'chiriladi. Qolgan ulanish sonini qaytaradi."""
        remaining = await self.client.decr(f"conn:{user_id}")
        if remaining <= 0:
            await self.client.delete(f"conn:{user_id}")
            await self.client.delete(self._presence_key(user_id))
            return 0
        return remaining

    async def is_online(self, user_id: int) -> bool:
        return bool(await self.client.exists(self._presence_key(user_id)))

    # ---------- Typing indicator ----------

    async def set_typing(self, chat_id: int, user_id: int) -> None:
        await self.client.setex(
            f"typing:{chat_id}:{user_id}", settings.TYPING_TTL, "1"
        )

    # ---------- Pub/Sub (realtime fan-out) ----------

    async def publish_event(self, event: dict[str, Any]) -> None:
        """Realtime eventni umumiy kanalga chiqaradi (barcha instance eshitadi)."""
        await self.client.publish(settings.RT_CHANNEL, json.dumps(event))

    async def subscribe_events(self) -> AsyncIterator[dict[str, Any]]:
        """RT kanalidagi eventlarni oqim sifatida qaytaradi."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(settings.RT_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    yield json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
        finally:
            await pubsub.unsubscribe(settings.RT_CHANNEL)
            await pubsub.aclose()


# Global instance
redis_service = RedisService()
