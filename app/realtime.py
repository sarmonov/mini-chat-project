"""Realtime fan-out yadrosi.

Barcha realtime eventlar Redis `rt:events` kanaliga chiqadi. Har bir instance
bitta subscriber task ishlatadi va eventni lokal ulangan WebSocketlarga yetkazadi.

Event formati:
    {"event": <str>, "recipients": [user_id, ...], "payload": {...}}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import distinct, select

from app.connection_manager import manager
from app.database import async_session_factory
from app.models import ChatMember, Message, User
from app.redis_service import redis_service
from app.schemas import MessageOut

logger = logging.getLogger("realtime")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------- Publish helperlar ----------------

async def publish_event(event: str, recipients: list[int], payload: dict) -> None:
    """Eventni Redis kanaliga chiqaradi (subscriber lokal WSlarga yetkazadi)."""
    await redis_service.publish_event(
        {"event": event, "recipients": list(set(recipients)), "payload": payload}
    )


async def notify_chat_update(chat_id: int, recipients: list[int]) -> None:
    """Suhbat o'zgardi (yangi suhbat, a'zolik) — klient ro'yxatni yangilasin."""
    await publish_event(
        "chat_update", recipients, {"type": "chat_update", "chat_id": chat_id}
    )


# ---------------- Xabar: saqlash + broadcast (RabbitMQ consumer chaqiradi) ----------------

async def persist_and_broadcast(job: dict) -> None:
    """RabbitMQ consumer'dan keladi: xabarni DB'ga saqlaydi va a'zolarga yuboradi."""
    chat_id = job["chat_id"]
    sender_id = job["sender_id"]

    async with async_session_factory() as db:
        msg = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=job.get("content") or "",
            media_url=job.get("media_url"),
            media_type=job.get("media_type"),
            media_name=job.get("media_name"),
            reply_to_id=job.get("reply_to_id"),
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        # yuboruvchining last_read'ini yangilaymiz (o'z xabari o'qilgan hisoblanadi)
        sender_member = await db.scalar(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id, ChatMember.user_id == sender_id
            )
        )
        if sender_member is not None:
            sender_member.last_read_message_id = msg.id
            await db.commit()

        recipients = list(
            await db.scalars(
                select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
            )
        )
        sender = await db.get(User, sender_id)

    payload = MessageOut.model_validate(msg).model_dump(mode="json")
    payload["type"] = "message"
    payload["client_id"] = job.get("client_id")  # optimistik UI moslashuvi uchun
    payload["sender_username"] = sender.username if sender else None
    payload["sender_name"] = sender.display_name if sender else None

    await publish_event("message", recipients, payload)


# ---------------- Typing ----------------

async def handle_typing(chat_id: int, user: User, recipients: list[int]) -> None:
    await redis_service.set_typing(chat_id, user.id)
    others = [uid for uid in recipients if uid != user.id]
    await publish_event(
        "typing",
        others,
        {
            "type": "typing",
            "chat_id": chat_id,
            "user_id": user.id,
            "user_name": user.display_name,
        },
    )


# ---------------- Read receipt ----------------

async def handle_read(chat_id: int, user_id: int, message_id: int, recipients: list[int]) -> None:
    async with async_session_factory() as db:
        member = await db.scalar(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
            )
        )
        if member is None:
            return
        if member.last_read_message_id is None or message_id > member.last_read_message_id:
            member.last_read_message_id = message_id
            await db.commit()

    await publish_event(
        "read",
        recipients,
        {
            "type": "read",
            "chat_id": chat_id,
            "user_id": user_id,
            "message_id": message_id,
        },
    )


# ---------------- Presence ----------------

async def contacts_of(user_id: int) -> list[int]:
    """Foydalanuvchi bilan kamida bitta umumiy suhbatga ega bo'lgan user id'lar."""
    async with async_session_factory() as db:
        my_chats = select(ChatMember.chat_id).where(ChatMember.user_id == user_id)
        rows = await db.scalars(
            select(distinct(ChatMember.user_id)).where(
                ChatMember.chat_id.in_(my_chats), ChatMember.user_id != user_id
            )
        )
        return list(rows)


async def broadcast_presence(user_id: int, online: bool) -> None:
    recipients = await contacts_of(user_id)
    if not recipients:
        return
    last_seen = None
    if not online:
        async with async_session_factory() as db:
            user = await db.get(User, user_id)
            if user is not None:
                user.last_seen = datetime.now(timezone.utc)
                await db.commit()
                last_seen = user.last_seen.isoformat()
    await publish_event(
        "presence",
        recipients,
        {"type": "presence", "user_id": user_id, "online": online, "last_seen": last_seen},
    )


# ---------------- Redis subscriber (background task) ----------------

async def redis_subscriber_loop() -> None:
    """Redis kanalidan eventlarni o'qib, lokal ulangan foydalanuvchilarga yuboradi."""
    logger.info("Redis subscriber ishga tushdi")
    async for event in redis_service.subscribe_events():
        recipients = event.get("recipients", [])
        payload = event.get("payload", {})
        try:
            await manager.send_to_users(recipients, payload)
        except Exception:  # noqa: BLE001
            logger.exception("Eventni yetkazishda xato")
