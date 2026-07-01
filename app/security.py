"""Parol hash (bcrypt) va JWT token yaratish/tekshirish."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Parolni bcrypt bilan hash qiladi."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    """JWT access token yaratadi (subject = user id)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Tokenni tekshiradi va user id qaytaradi. Xato bo'lsa None."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
