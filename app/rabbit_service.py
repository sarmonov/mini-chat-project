"""RabbitMQ — xabarni ishonchli saqlash quvuri.

Oqim:  WebSocket -> publish(persist job) -> RabbitMQ queue -> consumer
       -> PostgreSQL'ga saqlaydi -> Redis pub/sub orqali barcha a'zolarga broadcast.
"""
import json
import logging
from typing import Optional

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.config import settings

logger = logging.getLogger("rabbit")


class RabbitService:
    def __init__(self) -> None:
        self._connection: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._consumer_tag: Optional[str] = None

    @property
    def channel(self) -> AbstractChannel:
        if self._channel is None:
            raise RuntimeError("RabbitMQ ulanmagan. Avval connect() chaqiring.")
        return self._channel

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=20)
        # durable queue — server qayta ishga tushsa ham xabarlar yo'qolmaydi
        await self._channel.declare_queue(settings.MESSAGE_QUEUE, durable=True)
        logger.info("RabbitMQ ulandi, queue tayyor: %s", settings.MESSAGE_QUEUE)

    async def publish_persist(self, job: dict) -> None:
        """Xabarni saqlash uchun queue'ga job yuboradi."""
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(job).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=settings.MESSAGE_QUEUE,
        )

    async def start_consumer(self) -> None:
        """Saqlash consumer'ini ishga tushiradi."""
        queue = await self.channel.declare_queue(settings.MESSAGE_QUEUE, durable=True)
        self._consumer_tag = await queue.consume(self._on_message)
        logger.info("Consumer ishga tushdi: %s", settings.MESSAGE_QUEUE)

    async def _on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        # kech import — aylanma bog'liqlikni oldini olish uchun
        from app.realtime import persist_and_broadcast

        async with message.process():
            try:
                job = json.loads(message.body.decode())
                await persist_and_broadcast(job)
            except Exception:  # noqa: BLE001
                logger.exception("Xabarni saqlash/yuborishda xato")

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._channel = None


# Global instance
rabbit_service = RabbitService()
