"""FastAPI dependencylar — DB session va joriy foydalanuvchi (JWT)."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import User
from app.security import decode_access_token

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """`Authorization: Bearer <token>` sarlavhasidan foydalanuvchini aniqlaydi."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Avtorizatsiya token'i yo'q",
        )
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token yaroqsiz yoki muddati o'tgan",
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
