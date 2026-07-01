"""FastAPI ilova — WebSocket endpoint, lifecycle, RabbitMQ consumer broadcast."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import config
from app.connection_manager import manager
from app.models import IncomingMessage
from app.redis_service import redis_service
from app.rabbit_service import rabbit_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def on_rabbit_message(room: str, payload: dict) -> None:
    """Consumer queue'dan xabar olganda: Redis'ga saqlaydi + hammaga broadcast qiladi."""
    await redis_service.save_message(room, payload)
    await manager.broadcast(room, payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Redis + RabbitMQ ulanish, consumerlarni ishga tushirish
    await redis_service.connect()
    await rabbit_service.connect()
    await rabbit_service.start_consumers(on_rabbit_message)
    
    logger.info(f"Redis ulanish: {config.REDIS_URL}")
    logger.info(f"RabbitMQ ulanish: {config.RABBITMQ_URL}")
    
    logger.info("-" * 40)
    logger.info("Ilovaga kirish uchun manzillar (Ctrl ni bosib, ustiga cherting):")
    logger.info("👉 Loyiha URL: http://localhost:8000")
    logger.info("👉 Loyiha URL: http://127.0.0.1:8000")
    logger.info("👉 RabbitMQ UI: http://localhost:15672")
    logger.info("-" * 40)
    
    logger.info("Ilova ishga tushdi.")
    yield
    # Shutdown
    await rabbit_service.close()
    await redis_service.close()
    logger.info("Ilova to'xtatildi.")


app = FastAPI(title="Real-time Chat", lifespan=lifespan)

# static papkani ulaymiz
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/rooms")
async def rooms() -> dict:
    return {"rooms": config.ROOMS}


async def broadcast_online(room: str) -> None:
    users = await redis_service.get_online_users(room)
    await manager.broadcast(room, {"type": "online_users", "users": users})


@app.websocket("/ws/{room}/{username}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str) -> None:
    username = username.strip()

    # 1) Xona tekshiruvi
    if room not in config.ROOMS:
        await websocket.close(code=4004, reason="Bunday xona yo'q")
        return

    # 2) Bo'sh username tekshiruvi
    if not username:
        await websocket.close(code=4002, reason="Username bo'sh bo'lmasin")
        return

    # 3) Username band emasligini tekshirish (Redis Set)
    if await redis_service.is_username_taken(username):
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "message": f"'{username}' allaqachon band. Boshqa nom tanlang."}
        )
        await websocket.close(code=4001)
        return

    # 4) Ulanishni qabul qilamiz va ro'yxatga qo'shamiz
    await websocket.accept()
    await manager.connect(room, username, websocket)
    await redis_service.add_online_user(room, username)
    await redis_service.heartbeat(username)

    # 5) Yangi userga tarixni yuboramiz
    history = await redis_service.get_history(room)
    await manager.send_personal(websocket, {"type": "history", "messages": history})

    # 6) Online ro'yxat + kirdi notification
    await broadcast_online(room)
    await manager.broadcast(
        room,
        {"type": "notification", "event": "join", "username": username, "timestamp": now_iso()},
    )

    try:
        while True:
            raw = await websocket.receive_json()
            try:
                event = IncomingMessage(**raw)
            except ValidationError:
                await manager.send_personal(
                    websocket, {"type": "error", "message": "Noto'g'ri ma'lumot formati."}
                )
                continue

            if event.type == "message":
                await handle_chat_message(websocket, room, username, event)
            elif event.type == "typing":
                await handle_typing(room, username)
            elif event.type == "read":
                await handle_read(room, username, event)
            elif event.type == "heartbeat":
                await redis_service.heartbeat(username)

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("WebSocket xatosi (%s/%s)", room, username)
    finally:
        await manager.disconnect(room, username)
        await redis_service.remove_online_user(room, username)
        await broadcast_online(room)
        await manager.broadcast(
            room,
            {"type": "notification", "event": "leave", "username": username, "timestamp": now_iso()},
        )


async def handle_chat_message(
    websocket: WebSocket, room: str, username: str, event: IncomingMessage
) -> None:
    text = (event.message or "").strip()
    if not text:
        return

    # Rate limiting
    if not await redis_service.check_rate_limit(username):
        await manager.send_personal(
            websocket,
            {"type": "error", "message": "Juda tez yozyapsiz! Bir oz sekinroq 🐢"},
        )
        return

    message_id = await redis_service.next_message_id(room)
    payload = {
        "type": "message",
        "message_id": message_id,
        "username": username,
        "message": text,
        "room": room,
        "timestamp": now_iso(),
    }
    # RabbitMQ'ga publish -> consumer Redis'ga saqlaydi va broadcast qiladi
    await rabbit_service.publish(room, payload)


async def handle_typing(room: str, username: str) -> None:
    await redis_service.set_typing(room, username)
    await manager.broadcast(room, {"type": "typing", "username": username})


async def handle_read(room: str, username: str, event: IncomingMessage) -> None:
    if event.message_id is None:
        return
    await redis_service.set_last_read(room, username, event.message_id)
    await manager.broadcast(
        room,
        {"type": "read", "username": username, "message_id": event.message_id},
    )
