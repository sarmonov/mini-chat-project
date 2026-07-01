"""FastAPI ilova — routerlar, statik fayllar, lifecycle (DB/Redis/RabbitMQ)."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.rabbit_service import rabbit_service
from app.realtime import redis_subscriber_loop
from app.redis_service import redis_service
from app.routers import auth, chats, messages, upload, users
from app.ws import router as ws_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await init_db()
    await redis_service.connect()
    await rabbit_service.connect()
    await rabbit_service.start_consumer()

    # Redis subscriber background task (realtime fan-out)
    subscriber_task = asyncio.create_task(redis_subscriber_loop())

    logger.info("-" * 48)
    logger.info("Telegram-uslub chat ishga tushdi")
    logger.info("👉 Ilova:        http://localhost:8000")
    logger.info("👉 API docs:     http://localhost:8000/docs")
    logger.info("👉 RabbitMQ UI:  http://localhost:15672  (guest/guest)")
    logger.info("-" * 48)

    yield

    # --- Shutdown ---
    subscriber_task.cancel()
    await rabbit_service.close()
    await redis_service.close()
    logger.info("Ilova to'xtatildi.")


app = FastAPI(title="Mini Telegram", lifespan=lifespan)

# REST routerlar
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(upload.router)
# WebSocket
app.include_router(ws_router)

# Media fayllar (yuklamalar)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
# Frontend statik fayllar
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
