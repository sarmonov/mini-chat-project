"""Ro'yxatdan o'tish va kirish (JWT)."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import DbSession
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    exists = await db.scalar(select(User.id).where(User.username == payload.username))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu username allaqachon band")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Username yoki parol noto'g'ri")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))
