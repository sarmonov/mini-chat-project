"""Redis bilan ishlash — online users, tarix, typing, rate limit, read receipts."""
import json
from typing import Optional, Any

from redis.asyncio import Redis

from app import config


class RedisService:
    def __init__(self) -> None:
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Redis ulanmagan. Avval connect() chaqiring.")
        return self._client

    async def connect(self) -> None:
        self._client = Redis.from_url(config.REDIS_URL, decode_responses=True)
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ---------- Auth / Online users ----------

    async def is_username_taken(self, username: str) -> bool:
        """Username global online_users Set'da bormi (band emasligini tekshirish)."""
        return bool(await self.client.sismember("online_users", username))

    async def add_online_user(self, room: str, username: str) -> None:
        """Userni global va xona ro'yxatiga qo'shadi."""
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.sadd("online_users", username)
            pipe.sadd(f"online_users:{room}", username)
            await pipe.execute()

    async def remove_online_user(self, room: str, username: str) -> None:
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.srem("online_users", username)
            pipe.srem(f"online_users:{room}", username)
            pipe.delete(f"user:{username}:status")
            await pipe.execute()

    async def get_online_users(self, room: str) -> list[str]:
        users = await self.client.smembers(f"online_users:{room}")
        return sorted(users)

    # ---------- Heartbeat / Status ----------

    async def heartbeat(self, username: str) -> None:
        """user:{username}:status = online, 30 sekund TTL bilan."""
        await self.client.set(
            f"user:{username}:status", "online", ex=config.STATUS_TTL
        )

    # ---------- Chat tarixi ----------

    async def save_message(self, room: str, message: dict) -> None:
        """Xabarni xona tarixiga qo'shadi va oxirgi 50 tagacha kesadi."""
        key = f"chat_history:{room}"
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.lpush(key, json.dumps(message))
            pipe.ltrim(key, 0, config.HISTORY_LIMIT - 1)
            await pipe.execute()

    async def get_history(self, room: str) -> list[dict]:
        """Oxirgi 50 ta xabarni eski->yangi tartibida qaytaradi."""
        raw = await self.client.lrange(f"chat_history:{room}", 0, config.HISTORY_LIMIT - 1)
        # LPUSH bilan yangi xabar boshida turadi -> ko'rsatish uchun teskari qilamiz
        return [json.loads(item) for item in reversed(raw)]

    async def next_message_id(self, room: str) -> int:
        """Xona ichida ketma-ket xabar ID generatsiya qiladi (read receipt uchun)."""
        return await self.client.incr(f"msg_id:{room}")

    # ---------- Typing indicator ----------

    async def set_typing(self, room: str, username: str) -> None:
        """typing:{room}:{username} kaliti 3 sekundga o'rnatiladi."""
        await self.client.setex(f"typing:{room}:{username}", config.TYPING_TTL, "1")

    # ---------- Rate limiting ----------

    async def check_rate_limit(self, username: str) -> bool:
        """1 sekund oynasida RATE_LIMIT_MAX dan oshmaganini tekshiradi.

        True  -> ruxsat berildi
        False -> limitdan oshdi
        """
        key = f"rate:{username}"
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, config.RATE_LIMIT_WINDOW)
        return count <= config.RATE_LIMIT_MAX

    # ---------- Read receipts ----------

    async def set_last_read(self, room: str, username: str, message_id: int) -> None:
        """Har bir userning oxirgi o'qigan xabar ID'sini Hash'da saqlaydi."""
        await self.client.hset(f"read:{room}", username, message_id)

    async def get_read_state(self, room: str) -> dict[str, str]:
        return await self.client.hgetall(f"read:{room}")


# Global instance
redis_service = RedisService()
