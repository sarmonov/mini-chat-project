"""Ilova konfiguratsiyasi — barcha sozlamalar bir joyda (env / .env orqali override)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- PostgreSQL ----
    # asyncpg drayveri bilan async ulanish
    DATABASE_URL: str = "postgresql+asyncpg://chat:chat@localhost:5432/chat"

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- RabbitMQ ----
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # ---- Auth / JWT ----
    JWT_SECRET: str = "dev-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 kun

    # ---- Media ----
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_MB: int = 25

    # ---- Realtime ----
    PRESENCE_TTL: int = 30          # online heartbeat TTL (sekund)
    TYPING_TTL: int = 5             # typing indicator TTL (sekund)
    RT_CHANNEL: str = "rt:events"   # Redis pub/sub kanal (realtime fan-out)
    MESSAGE_QUEUE: str = "chat.persist"        # RabbitMQ queue (xabar saqlash)
    MESSAGE_EXCHANGE: str = "chat.messages"    # RabbitMQ exchange

    # ---- Xabar tarixi ----
    HISTORY_PAGE_SIZE: int = 50


settings = Settings()

# uploads papkasi mavjudligiga ishonch hosil qilamiz
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
