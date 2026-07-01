"""SQLAlchemy async engine, session factory va Base."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    """Barcha ORM modellar uchun asosiy klass."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — har so'rov uchun alohida DB session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Jadval sxemasini yaratadi (birinchi ishga tushirishda). Alembic o'rniga sodda yo'l."""
    # models import qilinishi shart — Base.metadata ga jadvallar ro'yxatga olinadi
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
