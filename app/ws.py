"""WebSocket endpoint — realtime kirish nuqtasi."""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import select

from app.chat_service import is_member, member_user_ids
from app.connection_manager import manager
from app.database import async_session_factory
from app.models import ChatMember, User
from app.rabbit_service import rabbit_service
from app.realtime import broadcast_presence, handle_read, handle_typing
from app.redis_service import redis_service
from app.schemas import WSIncoming
from app.security import decode_access_token

logger = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    # 1) Token orqali autentifikatsiya (query param: /ws?token=...)
    user_id = decode_access_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token yaroqsiz")
        return

    async with async_session_factory() as db:
        user = await db.get(User, user_id)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Foydalanuvchi topilmadi")
        return

    # 2) Ulanishni qabul qilamiz va ro'yxatga olamiz
    await websocket.accept()
    await manager.connect(user.id, websocket)
    await redis_service.mark_online(user.id)
    await broadcast_presence(user.id, online=True)

    try:
        while True:
            raw = await websocket.receive_json()

            # heartbeat — presence TTL'ni yangilaydi
            if isinstance(raw, dict) and raw.get("type") == "heartbeat":
                await redis_service.heartbeat(user.id)
                continue

            try:
                event = WSIncoming(**raw)
            except ValidationError:
                await websocket.send_json(
                    {"type": "error", "message": "Noto'g'ri ma'lumot formati"}
                )
                continue

            # har bir event uchun a'zolik tekshiruvi
            async with async_session_factory() as db:
                if not await is_member(db, event.chat_id, user.id):
                    await websocket.send_json(
                        {"type": "error", "message": "Siz bu suhbat a'zosi emassiz"}
                    )
                    continue
                recipients = await member_user_ids(db, event.chat_id)

            if event.type == "message":
                await handle_message(event, user)
            elif event.type == "typing":
                await handle_typing(event.chat_id, user, recipients)
            elif event.type == "read" and event.message_id is not None:
                await handle_read(event.chat_id, user.id, event.message_id, recipients)

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("WebSocket xatosi (user=%s)", user.id)
    finally:
        await manager.disconnect(user.id, websocket)
        remaining = await redis_service.mark_offline(user.id)
        if remaining == 0:
            await broadcast_presence(user.id, online=False)


async def handle_message(event: WSIncoming, user: User) -> None:
    """Xabarni RabbitMQ'ga saqlash uchun yuboradi (consumer DB + broadcast qiladi)."""
    content = (event.content or "").strip()
    if not content and not event.media_url:
        return  # bo'sh xabar

    job = {
        "chat_id": event.chat_id,
        "sender_id": user.id,
        "content": content,
        "media_url": event.media_url,
        "media_type": event.media_type,
        "media_name": event.media_name,
        "reply_to_id": event.reply_to_id,
        "client_id": getattr(event, "client_id", None),
    }
    await rabbit_service.publish_persist(job)
