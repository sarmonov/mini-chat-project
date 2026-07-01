"""Suhbat bilan bog'liq umumiy DB yordamchilari (REST va WebSocket ikkalasi ishlatadi)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Chat, ChatMember, ChatType, Message, User
from app.schemas import ChatOut, MemberOut, MessageOut, UserOut


async def is_member(db: AsyncSession, chat_id: int, user_id: int) -> bool:
    """Foydalanuvchi suhbat a'zosimi?"""
    row = await db.scalar(
        select(ChatMember.id).where(
            ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
        )
    )
    return row is not None


async def get_member(db: AsyncSession, chat_id: int, user_id: int) -> ChatMember | None:
    return await db.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id, ChatMember.user_id == user_id
        )
    )


async def member_user_ids(db: AsyncSession, chat_id: int) -> list[int]:
    """Suhbatning barcha a'zolari id'lari (realtime yetkazish uchun)."""
    rows = await db.scalars(
        select(ChatMember.user_id).where(ChatMember.chat_id == chat_id)
    )
    return list(rows)


async def find_private_chat(db: AsyncSession, user_a: int, user_b: int) -> Chat | None:
    """Ikki foydalanuvchi o'rtasidagi mavjud private suhbatni topadi."""
    m1 = select(ChatMember.chat_id).where(ChatMember.user_id == user_a).subquery()
    m2 = select(ChatMember.chat_id).where(ChatMember.user_id == user_b).subquery()
    chat_id = await db.scalar(
        select(Chat.id)
        .where(Chat.type == ChatType.private)
        .where(Chat.id.in_(select(m1.c.chat_id)))
        .where(Chat.id.in_(select(m2.c.chat_id)))
        .limit(1)
    )
    if chat_id is None:
        return None
    return await db.get(Chat, chat_id)


async def build_chat_out(db: AsyncSession, chat: Chat, viewer_id: int) -> ChatOut:
    """Chat ORM obyektini frontend uchun ChatOut'ga aylantiradi.

    - private suhbatda title/avatar qarama-qarshi foydalanuvchidan olinadi
    - oxirgi xabar va o'qilmagan xabarlar soni hisoblanadi
    """
    # a'zolarni user bilan birga yuklaymiz
    members = (
        await db.scalars(
            select(ChatMember)
            .where(ChatMember.chat_id == chat.id)
            .options(selectinload(ChatMember.user))
        )
    ).all()

    member_outs = [
        MemberOut(
            user=UserOut.model_validate(m.user),
            role=m.role,
            last_read_message_id=m.last_read_message_id,
        )
        for m in members
    ]

    title = chat.title
    avatar_url = chat.avatar_url
    if chat.type == ChatType.private:
        other = next((m.user for m in members if m.user.id != viewer_id), None)
        if other is not None:
            title = other.display_name
            avatar_url = other.avatar_url

    # oxirgi xabar
    last_msg = await db.scalar(
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.id.desc())
        .limit(1)
    )
    last_message = MessageOut.model_validate(last_msg) if last_msg else None

    # o'qilmagan xabarlar soni (viewer uchun)
    viewer_member = next((m for m in members if m.user_id == viewer_id), None)
    last_read = viewer_member.last_read_message_id if viewer_member else None
    unread_stmt = select(func.count(Message.id)).where(Message.chat_id == chat.id)
    if last_read is not None:
        unread_stmt = unread_stmt.where(Message.id > last_read)
    # o'z xabarlarini o'qilmagan deb sanamaymiz
    unread_stmt = unread_stmt.where(Message.sender_id != viewer_id)
    unread_count = await db.scalar(unread_stmt) or 0

    return ChatOut(
        id=chat.id,
        type=chat.type,
        title=title,
        avatar_url=avatar_url,
        members=member_outs,
        last_message=last_message,
        unread_count=unread_count,
    )


async def list_user_chats(db: AsyncSession, user_id: int) -> list[ChatOut]:
    """Foydalanuvchi a'zo bo'lgan barcha suhbatlar (oxirgi faollik bo'yicha)."""
    chat_ids = (
        await db.scalars(
            select(ChatMember.chat_id).where(ChatMember.user_id == user_id)
        )
    ).all()
    if not chat_ids:
        return []

    chats = (await db.scalars(select(Chat).where(Chat.id.in_(chat_ids)))).all()
    result = [await build_chat_out(db, chat, user_id) for chat in chats]

    # oxirgi xabar vaqti bo'yicha kamayish tartibida (xabarsizlar oxirida).
    # Kalit har doim timezone-aware datetime bo'lishi kerak (datetime<->int taqqoslanmaydi).
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    result.sort(
        key=lambda c: c.last_message.created_at if c.last_message else oldest,
        reverse=True,
    )
    return result
