"""Pydantic sxemalar — REST/WebSocket request va response modellari."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ChatType, MemberRole


# ---------------- Auth ----------------

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------- User ----------------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    bio: str = ""
    avatar_url: Optional[str] = None
    last_seen: Optional[datetime] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    bio: Optional[str] = Field(default=None, max_length=200)
    avatar_url: Optional[str] = Field(default=None, max_length=300)


# ---------------- Chat ----------------

class CreatePrivateRequest(BaseModel):
    user_id: int  # kim bilan suhbat ochish


class CreateGroupRequest(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    member_ids: list[int] = Field(default_factory=list)


class AddMemberRequest(BaseModel):
    user_id: int


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserOut
    role: MemberRole
    last_read_message_id: Optional[int] = None


class ChatOut(BaseModel):
    id: int
    type: ChatType
    title: Optional[str] = None
    avatar_url: Optional[str] = None
    members: list[MemberOut] = Field(default_factory=list)
    last_message: Optional[MessageOut] = None
    unread_count: int = 0


# ---------------- Message ----------------

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_id: Optional[int] = None
    content: str = ""
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_name: Optional[str] = None
    reply_to_id: Optional[int] = None
    is_deleted: bool = False
    edited_at: Optional[datetime] = None
    created_at: datetime


# ---------------- WebSocket ----------------

class WSIncoming(BaseModel):
    """Klientdan WebSocket orqali keladigan event."""
    type: Literal["message", "typing", "read"]
    chat_id: int
    content: Optional[str] = Field(default=None, max_length=4000)
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_name: Optional[str] = None
    reply_to_id: Optional[int] = None
    message_id: Optional[int] = None  # read event uchun
    client_id: Optional[str] = None   # optimistik UI moslashuvi uchun
