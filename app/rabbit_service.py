"""RabbitMQ bilan ishlash — har bir xona uchun alohida queue (publisher + consumer)."""
import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractChannel

from app import config

logger = logging.getLogger("rabbit")

# Consumer xabarni qabul qilganda chaqiriladigan callback turi
MessageHandler = Callable[[str, dict], Awaitable[None]]


def queue_name(room: str) -> str:
    """Har bir xona uchun alohida queue nomi: chat_messages:{room}."""
    return f"chat_messages:{room}"


class RabbitService:
    def __init__(self) -> None:
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._consumer_tasks: list[asyncio.Task] = []

    @property
    def channel(self) -> AbstractChannel:
        if self._channel is None:
            raise RuntimeError("RabbitMQ ulanmagan. Avval connect() chaqiring.")
        return self._channel

    async def connect(self) -> None:
        """Robust (avtomatik qayta ulanadigan) connection ochadi va queue'larni e'lon qiladi."""
        self._connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

        # Har bir xona uchun durable queue e'lon qilamiz
        for room in config.ROOMS:
            await self._channel.declare_queue(queue_name(room), durable=True)
        logger.info("RabbitMQ ulandi, queue'lar tayyor: %s", config.ROOMS)

    async def publish(self, room: str, message: dict) -> None:
        """Xabarni xona queue'siga publish qiladi."""
        body = json.dumps(message).encode()
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=queue_name(room),
        )

    async def start_consumers(self, handler: MessageHandler) -> None:
        """Har bir xona uchun consumer background task'ini ishga tushiradi."""
        for room in config.ROOMS:
            task = asyncio.create_task(self._consume_room(room, handler))
            self._consumer_tasks.append(task)

    async def _consume_room(self, room: str, handler: MessageHandler) -> None:
        queue = await self.channel.declare_queue(queue_name(room), durable=True)
        logger.info("Consumer ishga tushdi: %s", queue_name(room))
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        payload = json.loads(message.body.decode())
                        await handler(room, payload)
                    except Exception:  # noqa: BLE001
                        logger.exception("Consumer xabarni qayta ishlashda xato (%s)", room)

    async def close(self) -> None:
        for task in self._consumer_tasks:
            task.cancel()
        self._consumer_tasks.clear()
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None


# Global instance
rabbit_service = RabbitService()
