"""Pydantic modellar — WebSocket orqali keladigan/ketadigan ma'lumotlar."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """Klientdan WebSocket orqali keladigan event."""
    type: Literal["message", "typing", "read", "heartbeat"]
    message: Optional[str] = Field(default=None, max_length=2000)
    message_id: Optional[int] = None


class ChatMessage(BaseModel):
    """Chat xabari — RabbitMQ orqali yuriadi va tarixda saqlanadi."""
    type: Literal["message"] = "message"
    message_id: int
    username: str
    message: str
    room: str
    timestamp: str
