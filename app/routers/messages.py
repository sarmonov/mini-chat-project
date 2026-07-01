"""Xabar tarixi (sahifalash bilan)."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.chat_service import get_member, is_member
from app.config import settings
from app.deps import CurrentUser, DbSession
from app.models import Message
from app.schemas import MessageOut

router = APIRouter(prefix="/api/chats", tags=["messages"])


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
async def get_messages(
    chat_id: int,
    user: CurrentUser,
    db: DbSession,
    before_id: int | None = Query(default=None, description="Shu id'dan oldingilarni yuklaydi"),
    limit: int = Query(default=settings.HISTORY_PAGE_SIZE, ge=1, le=100),
) -> list[MessageOut]:
    if not await is_member(db, chat_id, user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")

    stmt = select(Message).where(Message.chat_id == chat_id)
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    stmt = stmt.order_by(Message.id.desc()).limit(limit)

    rows = (await db.scalars(stmt)).all()
    # eski -> yangi tartibda qaytaramiz (ko'rsatish uchun qulay)
    messages = [MessageOut.model_validate(m) for m in reversed(rows)]

    # tarixni ochgani — o'qildi deb belgilaymiz
    if messages:
        member = await get_member(db, chat_id, user.id)
        if member is not None:
            newest = max(m.id for m in messages)
            if member.last_read_message_id is None or newest > member.last_read_message_id:
                member.last_read_message_id = newest
                await db.commit()

    return messages
