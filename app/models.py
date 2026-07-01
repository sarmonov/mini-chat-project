"""SQLAlchemy ORM modellar — foydalanuvchi, suhbat, a'zolik, xabar."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatType(str, enum.Enum):
    private = "private"   # 1:1 suhbat
    group = "group"       # ko'p a'zoli guruh


class MemberRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    bio: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[ChatMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[ChatType] = mapped_column(Enum(ChatType, name="chat_type"), nullable=False)
    # guruh uchun nom; private uchun None (nom qarama-qarshi foydalanuvchidan olinadi)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    members: Mapped[list[ChatMember]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )


class ChatMember(Base):
    __tablename__ = "chat_members"
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_user"),
        Index("ix_member_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role"), default=MemberRole.member, nullable=False
    )
    # o'qilganlik holati (read receipt) — oxirgi o'qilgan xabar id
    last_read_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chat: Mapped[Chat] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id_id", "chat_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # media biriktirmasi (ixtiyoriy)
    media_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # image | file
    media_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    chat: Mapped[Chat] = relationship(back_populates="messages")
    sender: Mapped[User | None] = relationship()
